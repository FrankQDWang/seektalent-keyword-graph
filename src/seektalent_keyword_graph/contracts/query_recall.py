"""Public provider-aware query recall request and response contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

QueryRecallSchemaVersion = Literal[
    "query-recall-request-v1", "query-recall-response-v1"
]
RequirementStrength = Literal["required", "preferred", "nice_to_have"]
QueryMode = Literal["keyword", "exact", "phrase", "boolean"]
RecallBucket = Literal["healthy", "too_wide", "too_narrow", "zero", "stale", "unknown"]
ObservationStatus = Literal[
    "ok",
    "error",
    "timeout",
    "rate_limited",
    "server_error",
    "network_error",
    "auth_error",
    "unknown",
]
RecommendationAction = Literal[
    "keep",
    "downrank",
    "replace",
    "add_alias_probe",
    "add_precision_companion",
    "score_only",
    "fallback",
]
WarningCode = Literal[
    "unsupported_provider",
    "no_match",
    "matched_without_observation",
    "zero_recall",
    "too_wide_recall",
    "too_narrow_recall",
    "stale_observation",
    "unknown_observation",
    "fallback",
]
ReasonCode = Literal[
    "healthy_recall",
    "zero_recall",
    "too_wide_recall",
    "too_narrow_recall",
    "stale_observation",
    "unknown_observation",
    "no_match",
    "policy_blocked",
]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContractModel(BaseModel):
    """Base class for strict public query recall contracts."""

    model_config = ConfigDict(extra="forbid")


class QueryRecallRequestTerm(ContractModel):
    """One input term from a SeekTalent query term pool."""

    text: NonEmptyString
    strength: RequirementStrength = "required"
    source: NonEmptyString = "query_term_pool"


class QueryRecallObservation(ContractModel):
    """Provider-specific recall evidence selected from the runtime snapshot."""

    observation_id: NonEmptyString
    provider: NonEmptyString
    surface_id: NonEmptyString
    query_text: NonEmptyString
    query_hash: NonEmptyString
    query_mode: QueryMode
    total: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    status: ObservationStatus
    error_code: str | None = None
    observed_at: NonEmptyString
    recall_bucket: RecallBucket
    provider_api_version: NonEmptyString
    evidence_ref: str | None = None


class QueryRecallAlternative(ContractModel):
    """Graph-backed alternative candidate and optional provider observation."""

    query_text: NonEmptyString
    surface_id: NonEmptyString
    query_mode: QueryMode
    relation_type: NonEmptyString
    confidence: float = Field(ge=0.0, le=1.0)
    source_concept_id: str | None = None
    source_surface_id: NonEmptyString
    target_surface_id: NonEmptyString
    evidence_type: NonEmptyString
    evidence_ref: str | None = None
    observation: QueryRecallObservation | None = None


class QueryRecallRecommendation(ContractModel):
    """A concrete term-pool action with provider recall evidence."""

    action: RecommendationAction
    query_text: NonEmptyString
    recommended_query_text: str | None = None
    reason_code: ReasonCode
    reason: NonEmptyString
    provider: NonEmptyString
    evidence_observation_ids: list[str] = Field(default_factory=list)


class QueryRecallWarning(ContractModel):
    """Consumer-visible provider recall warning."""

    code: WarningCode
    message: NonEmptyString
    query_text: str | None = None
    provider: NonEmptyString


class OptimizedQueryTerm(ContractModel):
    """Ordered term-pool item emitted by query recall optimization."""

    query_text: NonEmptyString
    query_mode: QueryMode
    action: RecommendationAction
    rank: int = Field(ge=1)
    source_query_text: str | None = None
    provider: NonEmptyString
    recall_bucket: RecallBucket
    reason: NonEmptyString


class QueryRecallLineage(ContractModel):
    """Stable provenance for deterministic replay and debugging."""

    input_hash: NonEmptyString
    snapshot_schema_version: Literal["snapshot-v1"]
    selection_policy_version: Literal["policy-v1"]
    provider_sources: list[NonEmptyString] = Field(min_length=1)
    source_refs: list[str]


class QueryRecallRequest(ContractModel):
    """SeekTalent query recall analysis request."""

    schema_version: Literal["query-recall-request-v1"] = "query-recall-request-v1"
    request_id: NonEmptyString
    provider: NonEmptyString
    query_text: str | None = None
    query_terms: list[QueryRecallRequestTerm] = Field(default_factory=list)
    query_mode: QueryMode = "keyword"
    max_alternatives: int = Field(default=5, ge=0, le=50)
    max_precision_companions: int = Field(default=3, ge=0, le=20)

    @model_validator(mode="after")
    def validate_has_query_input(self) -> QueryRecallRequest:
        has_query_text = bool(self.query_text and self.query_text.strip())
        has_terms = bool(self.query_terms)
        if not (has_query_text or has_terms):
            raise ValueError(
                "request must include query_text or at least one query term"
            )
        return self


class QueryRecallResponse(ContractModel):
    """Keyword graph query recall analysis response."""

    schema_version: Literal["query-recall-response-v1"]
    request_id: NonEmptyString
    provider: NonEmptyString
    kg_snapshot_id: NonEmptyString
    selection_policy_version: Literal["policy-v1"]
    input_observations: list[QueryRecallObservation]
    alternatives: list[QueryRecallAlternative]
    recommendations: list[QueryRecallRecommendation]
    warnings: list[QueryRecallWarning]
    optimized_terms: list[OptimizedQueryTerm]
    lineage: QueryRecallLineage
