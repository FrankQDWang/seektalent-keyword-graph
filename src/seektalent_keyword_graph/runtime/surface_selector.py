"""Select trustworthy runtime surfaces and route them to bundle types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from seektalent_keyword_graph.contracts import QueryPlanWarning, RejectedSurface
from seektalent_keyword_graph.domain.policies import (
    ALIAS_PROBE_RECALL_BUCKETS,
    ANCHOR_RECALL_BUCKETS,
    EXPLORATION_RECALL_BUCKETS,
    REJECTION_REASON_RANK,
    WARNING_RANK,
)
from seektalent_keyword_graph.runtime.concept_resolver import (
    ResolvedInput,
    ResolvedTerm,
)
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore

_ALIAS_PROBE_RELATION_TYPES = (
    "alias",
    "abbreviation",
    "translation",
    "version_variant",
)
_MIN_COMPANION_SUPPORT = 0.5
_MIN_COMPANION_PMI = 1.0


@dataclass(frozen=True)
class RelatedSurface:
    surface: dict[str, Any]
    concept: dict[str, Any] | None
    confidence: float
    normalized_surface: str
    display_text: str


@dataclass(frozen=True)
class SelectedSurface:
    term: ResolvedTerm
    bundle_type: str
    companions: list[ResolvedTerm] = field(default_factory=list)
    aliases: list[RelatedSurface] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)

    @property
    def normalized_surface(self) -> str:
        return self.term.normalized_surface


@dataclass(frozen=True)
class SelectionResult:
    resolution: ResolvedInput
    selected: list[SelectedSurface]
    rejected_surfaces: list[RejectedSurface]
    warnings: list[QueryPlanWarning]


class SurfaceSelector:
    """Apply recall policy to resolved surfaces."""

    def __init__(self, store: SQLiteSnapshotStore) -> None:
        self.store = store

    def select(self, resolution: ResolvedInput) -> SelectionResult:
        selected: list[SelectedSurface] = []
        rejections: list[RejectedSurface] = []
        warning_terms: dict[str, list[str]] = {}

        for term in resolution.matched_terms:
            bucket = str(term.surface["recall_bucket"])
            if bucket in ANCHOR_RECALL_BUCKETS:
                selected.append(SelectedSurface(term=term, bundle_type="anchor"))
                continue
            if bucket == "too_wide":
                companions = self._companions(term, resolution.matched_terms)
                if companions:
                    selected.append(
                        SelectedSurface(
                            term=term,
                            bundle_type="precision",
                            companions=companions,
                        )
                    )
                else:
                    rejections.append(
                        RejectedSurface(
                            surface_text=term.text,
                            normalized_surface=term.normalized_surface,
                            reason_code="too_wide_without_companion",
                            source=term.source,
                            evidence=(
                                "Too-wide surface has no trusted companion in the "
                                "request."
                            ),
                        )
                    )
                continue
            if bucket in ALIAS_PROBE_RECALL_BUCKETS:
                aliases = self._aliases(term)
                if aliases:
                    warnings = ["stale_observation"] if bucket == "stale" else []
                    selected.append(
                        SelectedSurface(
                            term=term,
                            bundle_type="alias_probe",
                            aliases=aliases,
                            warning_codes=warnings,
                        )
                    )
                    if bucket == "stale":
                        warning_terms.setdefault("stale_observation", []).append(
                            term.text
                        )
                else:
                    reason = "stale_observation" if bucket == "stale" else "zero_recall"
                    rejections.append(
                        RejectedSurface(
                            surface_text=term.text,
                            normalized_surface=term.normalized_surface,
                            reason_code=reason,
                            source=term.source,
                            evidence=f"{bucket} recall surface has no active alias.",
                        )
                    )
                continue
            if bucket in EXPLORATION_RECALL_BUCKETS:
                if not resolution.request.include_exploration:
                    rejections.append(
                        RejectedSurface(
                            surface_text=term.text,
                            normalized_surface=term.normalized_surface,
                            reason_code="policy_blocked",
                            source=term.source,
                            evidence=(
                                "Exploration bundles are disabled for this request."
                            ),
                        )
                    )
                    continue
                selected.append(
                    SelectedSurface(
                        term=term,
                        bundle_type="exploration",
                        warning_codes=["unknown_observation"],
                    )
                )
                warning_terms.setdefault("unknown_observation", []).append(term.text)
                continue
            rejections.append(
                RejectedSurface(
                    surface_text=term.text,
                    normalized_surface=term.normalized_surface,
                    reason_code="policy_blocked",
                    source=term.source,
                    evidence=f"Recall bucket {bucket} is not selectable.",
                )
            )

        return SelectionResult(
            resolution=resolution,
            selected=selected,
            rejected_surfaces=sorted(
                rejections,
                key=lambda rejection: (
                    REJECTION_REASON_RANK.get(rejection.reason_code, 99),
                    rejection.normalized_surface,
                ),
            ),
            warnings=[
                QueryPlanWarning(
                    code=code,
                    message=_warning_message(code),
                    source_terms=terms,
                )
                for code, terms in sorted(
                    warning_terms.items(),
                    key=lambda item: WARNING_RANK.get(item[0], 99),
                )
            ],
        )

    def _companions(
        self, term: ResolvedTerm, matched_terms: list[ResolvedTerm]
    ) -> list[ResolvedTerm]:
        surface_id = str(term.surface["surface_id"])
        edge_companion_ids = {
            str(edge["surface_id_b"])
            if str(edge["surface_id_a"]) == surface_id
            else str(edge["surface_id_a"])
            for edge in self.store.list_cooccurrence_edges(surface_id)
            if _is_strong_cooccurrence(edge)
        }
        companion_by_surface_id = {
            str(other.surface["surface_id"]): other
            for other in matched_terms
            if other.normalized_surface != term.normalized_surface
            and str(other.surface["surface_id"]) in edge_companion_ids
            and str(other.surface["recall_bucket"]) == "healthy"
            and bool(other.surface["query_safe"])
        }
        for companion_id in edge_companion_ids:
            if companion_id in companion_by_surface_id:
                continue
            companion = self._graph_companion(term, companion_id)
            if companion is not None:
                companion_by_surface_id[companion_id] = companion

        return sorted(
            companion_by_surface_id.values(),
            key=lambda other: (
                -float(other.confidence),
                other.source_order,
                other.normalized_surface,
            ),
        )

    def _aliases(self, term: ResolvedTerm) -> list[RelatedSurface]:
        aliases: list[RelatedSurface] = []
        surface_id = str(term.surface["surface_id"])
        for relation in self.store.list_bidirectional_related_surfaces(
            surface_id, _ALIAS_PROBE_RELATION_TYPES
        ):
            related_surface_id = (
                str(relation["to_surface_id"])
                if str(relation["from_surface_id"]) == surface_id
                else str(relation["from_surface_id"])
            )
            surface = self.store.get_surface(related_surface_id)
            if surface is None or str(surface["serving_status"]) != "active":
                continue
            if not bool(surface["query_safe"]):
                continue
            concept = self._best_concept(str(surface["surface_id"]))
            aliases.append(
                RelatedSurface(
                    surface=surface,
                    concept=concept,
                    confidence=float(relation["confidence"]),
                    normalized_surface=str(surface["text_norm"]),
                    display_text=str(surface["display_text"]),
                )
            )
        return sorted(
            aliases,
            key=lambda alias: (-alias.confidence, alias.normalized_surface),
        )

    def _graph_companion(
        self, term: ResolvedTerm, companion_surface_id: str
    ) -> ResolvedTerm | None:
        surface = self.store.get_surface(companion_surface_id)
        if surface is None or str(surface["serving_status"]) != "active":
            return None
        if str(surface["recall_bucket"]) != "healthy" or not bool(
            surface["query_safe"]
        ):
            return None
        link = self._best_active_concept_link(companion_surface_id)
        if link is None:
            return None
        concept = self.store.get_concept(str(link["concept_id"]))
        if concept is None:
            return None
        return ResolvedTerm(
            text=str(surface["display_text"]),
            normalized_surface=str(surface["text_norm"]),
            source=term.source,
            strength="preferred",
            source_order=term.source_order,
            surface=surface,
            concept=concept,
            confidence=float(link["confidence"]),
            source_ref=f"graph_cooccurrence:{surface['text_norm']}",
        )

    def _best_concept(self, surface_id: str) -> dict[str, Any] | None:
        link = self._best_active_concept_link(surface_id)
        if link is not None:
            return self.store.get_concept(str(link["concept_id"]))
        return None

    def _best_active_concept_link(self, surface_id: str) -> dict[str, Any] | None:
        for link in self.store.list_surface_concepts(surface_id):
            if str(link["status"]) == "active":
                return link
        return None


def _warning_message(code: str) -> str:
    return {
        "stale_observation": "Selected surface has a stale recall observation.",
        "unknown_observation": "Selected surface has an unknown recall observation.",
    }[code]


def _is_strong_cooccurrence(edge: dict[str, Any]) -> bool:
    return (
        float(edge["support"]) >= _MIN_COMPANION_SUPPORT
        and float(edge["pmi"]) >= _MIN_COMPANION_PMI
    )
