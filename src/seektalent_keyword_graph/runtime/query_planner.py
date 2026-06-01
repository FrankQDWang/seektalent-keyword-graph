"""Public query-plan response orchestration."""

from __future__ import annotations

import hashlib
import json

from seektalent_keyword_graph.contracts import (
    ConceptSheetRow,
    QueryPlanLineage,
    QueryPlanRequest,
    QueryPlanResponse,
    QueryPlanWarning,
    RejectedSurface,
)
from seektalent_keyword_graph.domain.policies import (
    SELECTION_POLICY_VERSION,
    WARNING_RANK,
)
from seektalent_keyword_graph.runtime.bundle_builder import BundleBuilder
from seektalent_keyword_graph.runtime.concept_resolver import ConceptResolver
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.runtime.surface_selector import (
    SelectedSurface,
    SurfaceSelector,
)


class QueryPlanner:
    """Build deterministic query-plan responses from a runtime snapshot."""

    def __init__(self, store: SQLiteSnapshotStore) -> None:
        self.store = store

    def build(self, request: QueryPlanRequest) -> QueryPlanResponse:
        meta = self.store.meta()
        resolution = ConceptResolver(self.store).resolve(request)
        selection = SurfaceSelector(self.store).select(resolution)
        bundles = BundleBuilder().build(selection, request.max_query_bundles)
        fallback_terms = [
            term.text
            for term in resolution.no_match_terms
            if any(bundle.bundle_type == "fallback" for bundle in bundles)
        ]

        return QueryPlanResponse(
            schema_version="query-plan-response-v1",
            request_id=request.request_id,
            kg_snapshot_id=meta["kg_snapshot_id"],
            selection_policy_version=SELECTION_POLICY_VERSION,
            concept_sheet=self._concept_sheet(selection.selected),
            query_bundles=bundles,
            rejected_surfaces=self._rejections(
                resolution.rejected_surfaces, selection.rejected_surfaces
            ),
            warnings=self._warnings(
                no_match_terms=[term.text for term in resolution.no_match_terms],
                selection_warnings=selection.warnings,
                fallback_terms=fallback_terms,
            ),
            lineage=QueryPlanLineage(
                input_hash=_input_hash(request),
                snapshot_schema_version=meta["snapshot_schema_version"],
                selection_policy_version=SELECTION_POLICY_VERSION,
                source_refs=[
                    f"request:{request.request_id}",
                    f"snapshot:{meta['kg_snapshot_id']}",
                    *resolution.source_refs,
                ],
            ),
        )

    def _concept_sheet(
        self, selected_surfaces: list[SelectedSurface]
    ) -> list[ConceptSheetRow]:
        rows: list[ConceptSheetRow] = []
        for selected in selected_surfaces:
            term = selected.term
            selected_surface_texts = [str(term.surface["display_text"])]
            selected_surface_texts.extend(
                alias.display_text for alias in selected.aliases
            )
            selected_surface_texts.extend(
                str(companion.surface["display_text"])
                for companion in selected.companions
            )
            rows.append(
                ConceptSheetRow(
                    concept_id=str(term.concept["concept_id"]),
                    canonical_label=str(term.concept["canonical_label"]),
                    concept_type=str(term.concept["concept_type"]),
                    requirement_strength=term.strength,
                    matched_terms=[term.text],
                    selected_surfaces=selected_surface_texts,
                    recall_bucket=str(term.surface["recall_bucket"]),
                    confidence=term.confidence,
                )
            )
        return sorted(
            rows,
            key=lambda row: (
                row.requirement_strength != "required",
                row.canonical_label.casefold(),
                row.concept_id,
            ),
        )

    def _rejections(
        self,
        resolver_rejections: list[RejectedSurface],
        selector_rejections: list[RejectedSurface],
    ) -> list[RejectedSurface]:
        by_norm: dict[str, RejectedSurface] = {}
        for rejection in [*resolver_rejections, *selector_rejections]:
            by_norm.setdefault(rejection.normalized_surface, rejection)
        return list(by_norm.values())

    def _warnings(
        self,
        no_match_terms: list[str],
        selection_warnings: list[QueryPlanWarning],
        fallback_terms: list[str],
    ) -> list[QueryPlanWarning]:
        warnings: list[QueryPlanWarning] = []
        if no_match_terms:
            warnings.append(
                QueryPlanWarning(
                    code="no_match",
                    message="Some safe input terms had no active graph match.",
                    source_terms=no_match_terms,
                )
            )
        warnings.extend(selection_warnings)
        if fallback_terms:
            warnings.append(
                QueryPlanWarning(
                    code="fallback",
                    message=(
                        "Fallback bundle included because no graph route was "
                        "trustworthy."
                    ),
                    source_terms=fallback_terms,
                )
            )
        return sorted(warnings, key=lambda warning: WARNING_RANK.get(warning.code, 99))


def _input_hash(request: QueryPlanRequest) -> str:
    payload = request.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
