"""Provider-aware query recall optimization from local snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from seektalent_keyword_graph.contracts import (
    OptimizedQueryTerm,
    QueryRecallAlternative,
    QueryRecallLineage,
    QueryRecallObservation,
    QueryRecallRecommendation,
    QueryRecallRequest,
    QueryRecallResponse,
    QueryRecallWarning,
)
from seektalent_keyword_graph.domain.normalization import normalize_surface
from seektalent_keyword_graph.runtime.errors import KeywordGraphRuntimeError
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore

_ALTERNATIVE_RELATION_TYPES = (
    "alias",
    "abbreviation",
    "equivalent",
    "normalized",
    "normalized_form",
    "translation",
    "version",
    "version_variant",
)
_BUCKET_RANK = {
    "healthy": 0,
    "too_narrow": 1,
    "unknown": 2,
    "stale": 3,
    "too_wide": 4,
    "zero": 5,
}
_WARNING_RANK = {
    "no_match": 0,
    "zero_recall": 10,
    "too_wide_recall": 20,
    "too_narrow_recall": 30,
    "stale_observation": 40,
    "unknown_observation": 50,
    "matched_without_observation": 60,
    "fallback": 70,
}


@dataclass(frozen=True)
class _InputTerm:
    text: str
    normalized_text: str
    source: str
    order: int


@dataclass(frozen=True)
class _MatchedTerm:
    input_term: _InputTerm
    surface: dict[str, Any]
    concept: dict[str, Any] | None
    observation: QueryRecallObservation | None

    @property
    def bucket(self) -> str:
        if self.observation is None:
            return "unknown"
        return self.observation.recall_bucket


class QueryRecallOptimizer:
    """Analyze and optimize query terms using only local snapshot rows."""

    def __init__(self, store: SQLiteSnapshotStore) -> None:
        self.store = store

    def analyze(self, request: QueryRecallRequest) -> QueryRecallResponse:
        providers = self.store.list_supported_providers()
        if request.provider not in providers:
            raise KeywordGraphRuntimeError(
                f"unsupported provider: {request.provider}"
            )

        meta = self.store.meta()
        input_terms = _input_terms(request)
        matched_terms: list[_MatchedTerm] = []
        no_match_terms: list[_InputTerm] = []

        for term in input_terms:
            matched = self._resolve_term(request, term)
            if matched is None:
                no_match_terms.append(term)
            else:
                matched_terms.append(matched)

        all_alternatives = self._alternatives(request, matched_terms)
        recommendations = self._recommendations(
            request, matched_terms, no_match_terms, all_alternatives
        )
        response_alternatives = _response_alternatives(
            all_alternatives, recommendations, matched_terms, request.max_alternatives
        )
        optimized_terms = _optimized_terms(
            recommendations, all_alternatives, matched_terms
        )

        return QueryRecallResponse(
            schema_version="query-recall-response-v1",
            request_id=request.request_id,
            provider=request.provider,
            kg_snapshot_id=meta["kg_snapshot_id"],
            selection_policy_version="policy-v1",
            input_observations=[
                matched.observation
                for matched in matched_terms
                if matched.observation is not None
            ],
            alternatives=response_alternatives,
            recommendations=recommendations,
            warnings=_warnings(matched_terms, no_match_terms, recommendations, request),
            optimized_terms=optimized_terms,
            lineage=QueryRecallLineage(
                input_hash=_input_hash(request),
                snapshot_schema_version="snapshot-v1",
                selection_policy_version="policy-v1",
                provider_sources=providers,
                source_refs=_source_refs(
                    request, meta["kg_snapshot_id"], matched_terms
                ),
            ),
        )

    def _resolve_term(
        self, request: QueryRecallRequest, term: _InputTerm
    ) -> _MatchedTerm | None:
        surface = self.store.get_surface_by_query_text(
            request.provider, term.text, request.query_mode
        )
        if surface is None:
            surface = self.store.get_surface_by_norm(term.normalized_text)
        if surface is None or str(surface["serving_status"]) != "active":
            return None
        if not bool(surface["query_safe"]):
            return None

        concept = self._best_concept(str(surface["surface_id"]))
        observation = self._observation(
            request.provider, str(surface["surface_id"]), request.query_mode
        )
        return _MatchedTerm(
            input_term=term,
            surface=surface,
            concept=concept,
            observation=observation,
        )

    def _alternatives(
        self, request: QueryRecallRequest, matched_terms: list[_MatchedTerm]
    ) -> list[QueryRecallAlternative]:
        alternatives_by_key: dict[tuple[str, str], QueryRecallAlternative] = {}
        for matched in matched_terms:
            source_surface_id = str(matched.surface["surface_id"])
            for relation in self.store.list_bidirectional_related_surfaces(
                source_surface_id, _ALTERNATIVE_RELATION_TYPES
            ):
                target_surface_id = _relation_target(relation, source_surface_id)
                alternative = self._alternative_from_surface(
                    request=request,
                    matched=matched,
                    target_surface_id=target_surface_id,
                    relation_type=str(relation["relation_type"]),
                    confidence=float(relation["confidence"]),
                    evidence_type=str(relation["evidence_type"]),
                    evidence_ref=str(relation["relation_id"]),
                )
                if alternative is not None:
                    alternatives_by_key.setdefault(
                        (
                            alternative.source_surface_id,
                            alternative.target_surface_id,
                            alternative.relation_type,
                        ),
                        alternative,
                    )

            for concept_link in self._same_concept_links(matched):
                target_surface_id = str(concept_link["surface_id"])
                if target_surface_id == source_surface_id:
                    continue
                key = (source_surface_id, target_surface_id, "equivalent")
                if key in alternatives_by_key:
                    continue
                alternative = self._alternative_from_surface(
                    request=request,
                    matched=matched,
                    target_surface_id=target_surface_id,
                    relation_type="equivalent",
                    confidence=float(concept_link["confidence"]),
                    evidence_type=str(concept_link["source"]),
                    evidence_ref=(
                        f"concept_surface:{concept_link['concept_id']}:"
                        f"{target_surface_id}"
                    ),
                )
                if alternative is not None:
                    alternatives_by_key[key] = alternative

            if matched.bucket == "too_wide":
                for edge in self.store.list_cooccurrence_edges(source_surface_id):
                    target_surface_id = (
                        str(edge["surface_id_b"])
                        if str(edge["surface_id_a"]) == source_surface_id
                        else str(edge["surface_id_a"])
                    )
                    alternative = self._alternative_from_surface(
                        request=request,
                        matched=matched,
                        target_surface_id=target_surface_id,
                        relation_type="cooccurrence",
                        confidence=float(edge["support"]),
                        evidence_type=str(edge["window_type"]),
                        evidence_ref=str(edge["edge_id"]),
                    )
                    if alternative is not None:
                        alternatives_by_key.setdefault(
                            (
                                alternative.source_surface_id,
                                alternative.target_surface_id,
                                alternative.relation_type,
                            ),
                            alternative,
                        )

        return sorted(
            alternatives_by_key.values(),
            key=self._alternative_sort_key,
        )

    def _alternative_from_surface(
        self,
        *,
        request: QueryRecallRequest,
        matched: _MatchedTerm,
        target_surface_id: str,
        relation_type: str,
        confidence: float,
        evidence_type: str,
        evidence_ref: str,
    ) -> QueryRecallAlternative | None:
        source_surface_id = str(matched.surface["surface_id"])
        if target_surface_id == source_surface_id:
            return None
        surface = self.store.get_surface(target_surface_id)
        if surface is None or str(surface["serving_status"]) != "active":
            return None
        if not bool(surface["query_safe"]):
            return None
        observation = self._observation(
            request.provider, target_surface_id, request.query_mode
        )
        return QueryRecallAlternative(
            query_text=str(surface["display_text"]),
            surface_id=target_surface_id,
            query_mode=request.query_mode,
            relation_type=relation_type,
            confidence=confidence,
            source_concept_id=(
                None
                if matched.concept is None
                else str(matched.concept["concept_id"])
            ),
            source_surface_id=source_surface_id,
            target_surface_id=target_surface_id,
            evidence_type=evidence_type,
            evidence_ref=evidence_ref,
            observation=observation,
        )

    def _recommendations(
        self,
        request: QueryRecallRequest,
        matched_terms: list[_MatchedTerm],
        no_match_terms: list[_InputTerm],
        alternatives: list[QueryRecallAlternative],
    ) -> list[QueryRecallRecommendation]:
        recommendations: list[QueryRecallRecommendation] = []
        alternatives_by_source: dict[str, list[QueryRecallAlternative]] = {}
        for alternative in alternatives:
            alternatives_by_source.setdefault(alternative.source_surface_id, []).append(
                alternative
            )

        for matched in matched_terms:
            bucket = matched.bucket
            input_text = matched.input_term.text
            source_surface_id = str(matched.surface["surface_id"])
            candidate = _best_replacement(
                alternatives_by_source.get(source_surface_id, [])
            )
            evidence_ids = _evidence_ids(matched.observation, candidate)

            if bucket == "healthy":
                recommendations.append(
                    _recommendation(
                        action="keep",
                        query_text=input_text,
                        recommended_query_text=input_text,
                        reason_code="healthy_recall",
                        reason="Input term has healthy provider recall.",
                        provider=request.provider,
                        evidence_ids=evidence_ids,
                    )
                )
                continue
            if bucket == "too_wide":
                companion = _best_companion(
                    alternatives_by_source.get(source_surface_id, []),
                    request.max_precision_companions,
                )
                if companion is not None:
                    recommendations.append(
                        _recommendation(
                            action="add_precision_companion",
                            query_text=input_text,
                            recommended_query_text=companion.query_text,
                            reason_code="too_wide_recall",
                            reason=(
                                "Input term is too wide and companion has "
                                "healthier provider recall."
                            ),
                            provider=request.provider,
                            evidence_ids=_evidence_ids(matched.observation, companion),
                        )
                    )
                else:
                    recommendations.append(
                        _recommendation(
                            action="downrank",
                            query_text=input_text,
                            recommended_query_text=None,
                            reason_code="too_wide_recall",
                            reason="Input term is too wide with no healthy companion.",
                            provider=request.provider,
                            evidence_ids=evidence_ids,
                        )
                    )
                continue
            if bucket in {"zero", "too_narrow", "stale"} and candidate is not None:
                recommendations.append(
                    _recommendation(
                        action="replace",
                        query_text=input_text,
                        recommended_query_text=candidate.query_text,
                        reason_code=_reason_code(bucket),
                        reason="Graph alternative has healthier provider recall.",
                        provider=request.provider,
                        evidence_ids=evidence_ids,
                    )
                )
                continue
            recommendations.append(
                _recommendation(
                    action="score_only",
                    query_text=input_text,
                    recommended_query_text=None,
                    reason_code=_reason_code(bucket),
                    reason="Input term should contribute only as scoring context.",
                    provider=request.provider,
                    evidence_ids=evidence_ids,
                )
            )

        for term in no_match_terms:
            recommendations.append(
                _recommendation(
                    action="fallback",
                    query_text=term.text,
                    recommended_query_text=None,
                    reason_code="no_match",
                    reason="Input term had no active graph match.",
                    provider=request.provider,
                    evidence_ids=[],
                )
            )

        return recommendations

    def _same_concept_links(self, matched: _MatchedTerm) -> list[dict[str, Any]]:
        if matched.concept is None:
            return []
        return [
            link
            for link in self.store.list_concept_surfaces(
                str(matched.concept["concept_id"])
            )
            if str(link["status"]) == "active"
        ]

    def _best_concept(self, surface_id: str) -> dict[str, Any] | None:
        for link in self.store.list_surface_concepts(surface_id):
            if str(link["status"]) != "active":
                continue
            return self.store.get_concept(str(link["concept_id"]))
        return None

    def _observation(
        self, provider: str, surface_id: str, query_mode: str
    ) -> QueryRecallObservation | None:
        row = self.store.get_latest_surface_recall_observation(
            provider, surface_id, query_mode
        )
        if row is None:
            return None
        return QueryRecallObservation(
            observation_id=str(row["observation_id"]),
            provider=str(row["provider"]),
            surface_id=str(row["surface_id"]),
            query_text=str(row["query_text"]),
            query_hash=str(row["query_hash"]),
            query_mode=str(row["query_mode"]),
            total=None if row["total"] is None else int(row["total"]),
            latency_ms=None
            if row["latency_ms"] is None
            else int(row["latency_ms"]),
            status=str(row["status"]),
            error_code=None if row["error_code"] is None else str(row["error_code"]),
            observed_at=str(row["observed_at"]),
            recall_bucket=str(row["recall_bucket"]),
            provider_api_version=str(row["provider_api_version"]),
            evidence_ref=None
            if row["evidence_ref"] is None
            else str(row["evidence_ref"]),
        )

    def _alternative_sort_key(
        self, alternative: QueryRecallAlternative
    ) -> tuple[int, float, float, float, str]:
        bucket = (
            "unknown"
            if alternative.observation is None
            else alternative.observation.recall_bucket
        )
        surface = self.store.get_surface(alternative.target_surface_id) or {}
        specificity = float(surface.get("specificity_score", 0.0))
        ambiguity = float(surface.get("ambiguity_score", 0.0))
        return (
            _BUCKET_RANK.get(bucket, 99),
            -alternative.confidence,
            -specificity,
            ambiguity,
            alternative.query_text.casefold(),
        )


def _input_terms(request: QueryRecallRequest) -> list[_InputTerm]:
    raw_terms: list[tuple[str, str]] = []
    if request.query_text and request.query_text.strip():
        raw_terms.append((request.query_text.strip(), "query_text"))
    raw_terms.extend((term.text, term.source) for term in request.query_terms)

    terms: list[_InputTerm] = []
    seen: set[tuple[str, str, str]] = set()
    for order, (text, source) in enumerate(raw_terms):
        normalized_text = normalize_surface(text).text_norm
        key = (request.provider, request.query_mode, normalized_text)
        if key in seen:
            continue
        seen.add(key)
        terms.append(
            _InputTerm(
                text=text,
                normalized_text=normalized_text,
                source=source,
                order=order,
            )
        )
    return terms


def _optimized_terms(
    recommendations: list[QueryRecallRecommendation],
    alternatives: list[QueryRecallAlternative],
    matched_terms: list[_MatchedTerm],
) -> list[OptimizedQueryTerm]:
    alternatives_by_text = {
        (alternative.source_surface_id, alternative.query_text): alternative
        for alternative in alternatives
    }
    matched_by_text = {matched.input_term.text: matched for matched in matched_terms}
    optimized: list[OptimizedQueryTerm] = []
    for recommendation in recommendations:
        matched = matched_by_text.get(recommendation.query_text)
        if recommendation.action == "add_precision_companion" and matched is not None:
            optimized.append(
                OptimizedQueryTerm(
                    query_text=recommendation.query_text,
                    query_mode=(
                        matched.observation.query_mode
                        if matched.observation is not None
                        else "keyword"
                    ),
                    action="keep",
                    rank=len(optimized) + 1,
                    source_query_text=recommendation.query_text,
                    provider=recommendation.provider,
                    recall_bucket=matched.bucket,
                    reason="Original term retained while adding precision companion.",
                )
            )
        query_text = recommendation.recommended_query_text or recommendation.query_text
        source_surface_id = (
            "" if matched is None else str(matched.surface["surface_id"])
        )
        alternative = alternatives_by_text.get((source_surface_id, query_text))
        bucket = "unknown"
        if alternative is not None and alternative.observation is not None:
            bucket = alternative.observation.recall_bucket
        elif matched is not None:
            bucket = matched.bucket
        query_mode = "keyword"
        if matched is not None and matched.observation is not None:
            query_mode = matched.observation.query_mode
        optimized.append(
            OptimizedQueryTerm(
                query_text=query_text,
                query_mode=query_mode,
                action=recommendation.action,
                rank=len(optimized) + 1,
                source_query_text=recommendation.query_text,
                provider=recommendation.provider,
                recall_bucket=bucket,
                reason=recommendation.reason,
            )
        )
    return optimized


def _response_alternatives(
    alternatives: list[QueryRecallAlternative],
    recommendations: list[QueryRecallRecommendation],
    matched_terms: list[_MatchedTerm],
    max_alternatives: int,
) -> list[QueryRecallAlternative]:
    matched_by_text = {matched.input_term.text: matched for matched in matched_terms}
    alternatives_by_key: dict[tuple[str, str], QueryRecallAlternative] = {}
    for alternative in alternatives:
        alternatives_by_key.setdefault(
            (alternative.source_surface_id, alternative.query_text),
            alternative,
        )
    required: list[QueryRecallAlternative] = []
    seen: set[tuple[str, str, str]] = set()
    for recommendation in recommendations:
        if recommendation.recommended_query_text is None:
            continue
        matched = matched_by_text.get(recommendation.query_text)
        if matched is None:
            continue
        key = (
            str(matched.surface["surface_id"]),
            recommendation.recommended_query_text,
        )
        alternative = alternatives_by_key.get(key)
        if alternative is None:
            continue
        identity = (
            alternative.source_surface_id,
            alternative.query_text,
            alternative.relation_type,
        )
        if identity in seen:
            continue
        seen.add(identity)
        required.append(alternative)

    response = list(required)
    limit = max(max_alternatives, len(required))
    for alternative in alternatives:
        identity = (
            alternative.source_surface_id,
            alternative.query_text,
            alternative.relation_type,
        )
        if identity in seen:
            continue
        if len(response) >= limit:
            break
        seen.add(identity)
        response.append(alternative)
    return response


def _warnings(
    matched_terms: list[_MatchedTerm],
    no_match_terms: list[_InputTerm],
    recommendations: list[QueryRecallRecommendation],
    request: QueryRecallRequest,
) -> list[QueryRecallWarning]:
    warnings: list[QueryRecallWarning] = []
    for term in no_match_terms:
        warnings.append(
            QueryRecallWarning(
                code="no_match",
                message="Input term had no active graph match.",
                query_text=term.text,
                provider=request.provider,
            )
        )
    for matched in matched_terms:
        code = _warning_code(matched.bucket)
        if code is None:
            continue
        warnings.append(
            QueryRecallWarning(
                code=code,
                message=_warning_message(code),
                query_text=matched.input_term.text,
                provider=request.provider,
            )
        )
        if matched.observation is None:
            warnings.append(
                QueryRecallWarning(
                    code="matched_without_observation",
                    message="Input term matched graph but has no provider observation.",
                    query_text=matched.input_term.text,
                    provider=request.provider,
                )
            )
    for recommendation in recommendations:
        if recommendation.action != "fallback":
            continue
        warnings.append(
            QueryRecallWarning(
                code="fallback",
                message="Fallback action emitted for unmatched input term.",
                query_text=recommendation.query_text,
                provider=request.provider,
            )
        )
    return sorted(
        warnings,
        key=lambda warning: (
            _WARNING_RANK.get(warning.code, 99),
            "" if warning.query_text is None else warning.query_text.casefold(),
        ),
    )


def _recommendation(
    *,
    action: str,
    query_text: str,
    recommended_query_text: str | None,
    reason_code: str,
    reason: str,
    provider: str,
    evidence_ids: list[str],
) -> QueryRecallRecommendation:
    return QueryRecallRecommendation(
        action=action,
        query_text=query_text,
        recommended_query_text=recommended_query_text,
        reason_code=reason_code,
        reason=reason,
        provider=provider,
        evidence_observation_ids=evidence_ids,
    )


def _best_replacement(
    alternatives: list[QueryRecallAlternative],
) -> QueryRecallAlternative | None:
    healthy = [
        alternative
        for alternative in alternatives
        if alternative.relation_type != "cooccurrence"
        and alternative.observation is not None
        and alternative.observation.recall_bucket == "healthy"
    ]
    if not healthy:
        return None
    return healthy[0]


def _best_companion(
    alternatives: list[QueryRecallAlternative], limit: int
) -> QueryRecallAlternative | None:
    if limit <= 0:
        return None
    companions = [
        alternative
        for alternative in alternatives
        if alternative.relation_type == "cooccurrence"
        and alternative.observation is not None
        and alternative.observation.recall_bucket == "healthy"
    ]
    if not companions:
        return None
    return companions[0]


def _evidence_ids(
    observation: QueryRecallObservation | None,
    alternative: QueryRecallAlternative | None,
) -> list[str]:
    ids: list[str] = []
    if observation is not None:
        ids.append(observation.observation_id)
    if alternative is not None and alternative.observation is not None:
        ids.append(alternative.observation.observation_id)
    return ids


def _relation_target(relation: dict[str, Any], source_surface_id: str) -> str:
    if str(relation["from_surface_id"]) == source_surface_id:
        return str(relation["to_surface_id"])
    return str(relation["from_surface_id"])


def _warning_code(bucket: str) -> str | None:
    return {
        "zero": "zero_recall",
        "too_wide": "too_wide_recall",
        "too_narrow": "too_narrow_recall",
        "stale": "stale_observation",
        "unknown": "unknown_observation",
    }.get(bucket)


def _warning_message(code: str) -> str:
    return {
        "zero_recall": "Input term has zero observed recall.",
        "too_wide_recall": "Input term has too-wide observed recall.",
        "too_narrow_recall": "Input term has too-narrow observed recall.",
        "stale_observation": "Input term has a stale provider observation.",
        "unknown_observation": "Input term has an unknown provider observation.",
    }[code]


def _reason_code(bucket: str) -> str:
    return {
        "zero": "zero_recall",
        "too_wide": "too_wide_recall",
        "too_narrow": "too_narrow_recall",
        "stale": "stale_observation",
        "unknown": "unknown_observation",
    }.get(bucket, "policy_blocked")


def _input_hash(request: QueryRecallRequest) -> str:
    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _source_refs(
    request: QueryRecallRequest,
    snapshot_id: str,
    matched_terms: list[_MatchedTerm],
) -> list[str]:
    refs = [
        f"request:{request.request_id}",
        f"snapshot:{snapshot_id}",
        f"provider:{request.provider}",
    ]
    for matched in matched_terms:
        refs.append(f"surface:{matched.surface['surface_id']}")
        if matched.concept is not None:
            refs.append(f"concept:{matched.concept['concept_id']}")
        if matched.observation is not None:
            refs.append(f"observation:{matched.observation.observation_id}")
    return refs
