"""Build public query bundles from selected runtime surfaces."""

from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryBundle, QueryPlanQuery
from seektalent_keyword_graph.domain.scoring import bundle_sort_key
from seektalent_keyword_graph.runtime.surface_selector import (
    SelectedSurface,
    SelectionResult,
)


class BundleBuilder:
    """Convert selected surfaces into deterministic query bundle contracts."""

    def build(
        self, selection: SelectionResult, max_query_bundles: int
    ) -> list[QueryBundle]:
        bundles = [
            self._bundle_for_selected(selected) for selected in selection.selected
        ]
        if not bundles:
            bundles = self._fallback_bundles(selection)

        sorted_bundles = sorted(
            bundles,
            key=lambda bundle: (
                bundle_sort_key(
                    bundle.bundle_type,
                    _strength_for_bundle(selection, bundle.label),
                    _source_order_for_bundle(selection, bundle.label),
                    bundle.label,
                    **_quality_for_bundle(selection, bundle.label),
                )
            ),
        )
        deduped_bundles = _dedupe_by_executable_query(sorted_bundles)[
            :max_query_bundles
        ]

        return [
            bundle.model_copy(update={"priority": index})
            for index, bundle in enumerate(deduped_bundles, start=1)
        ]

    def _bundle_for_selected(self, selected: SelectedSurface) -> QueryBundle:
        if selected.bundle_type == "anchor":
            return self._anchor(selected)
        if selected.bundle_type == "precision":
            return self._precision(selected)
        if selected.bundle_type == "alias_probe":
            return self._alias_probe(selected)
        return self._exploration(selected)

    def _anchor(self, selected: SelectedSurface) -> QueryBundle:
        display = str(selected.term.surface["display_text"])
        concept_id = str(selected.term.concept["concept_id"])
        return QueryBundle(
            bundle_type="anchor",
            label=f"{display} anchor",
            queries=[
                QueryPlanQuery(
                    query_text=_quoted(display),
                    query_mode="exact",
                    surfaces=[display],
                    reason=(
                        "Required or extracted concept with healthy observed recall."
                    ),
                    priority=1,
                    source_concept_ids=[concept_id],
                    recall_bucket="healthy",
                )
            ],
            rationale="Selected graph surface has healthy observed recall.",
            priority=1,
            source_concept_ids=[concept_id],
            warnings=[],
        )

    def _precision(self, selected: SelectedSurface) -> QueryBundle:
        display = str(selected.term.surface["display_text"])
        companion = selected.companions[0]
        companion_display = str(companion.surface["display_text"])
        concept_ids = [
            str(selected.term.concept["concept_id"]),
            str(companion.concept["concept_id"]),
        ]
        return QueryBundle(
            bundle_type="precision",
            label=f"{display} precision",
            queries=[
                QueryPlanQuery(
                    query_text=f"{_quoted(display)} {_quoted(companion_display)}",
                    query_mode="boolean",
                    surfaces=[display, companion_display],
                    reason="Too-wide surface paired with a trusted companion term.",
                    priority=1,
                    source_concept_ids=concept_ids,
                    recall_bucket="too_wide",
                )
            ],
            rationale="Companion term narrows a high-recall surface.",
            priority=1,
            source_concept_ids=concept_ids,
            warnings=[],
        )

    def _alias_probe(self, selected: SelectedSurface) -> QueryBundle:
        display = str(selected.term.surface["display_text"])
        alias = selected.aliases[0]
        concept_id = str(selected.term.concept["concept_id"])
        return QueryBundle(
            bundle_type="alias_probe",
            label=f"{display} alias probe",
            queries=[
                QueryPlanQuery(
                    query_text=_quoted(alias.display_text),
                    query_mode="exact",
                    surfaces=[alias.display_text],
                    reason=(
                        "Primary surface has weak recall; active alias is safer to "
                        "probe."
                    ),
                    priority=1,
                    source_concept_ids=[concept_id],
                    recall_bucket=str(selected.term.surface["recall_bucket"]),
                )
            ],
            rationale="Alias relation provides an alternative graph-backed surface.",
            priority=1,
            source_concept_ids=[concept_id],
            warnings=selected.warning_codes,
        )

    def _exploration(self, selected: SelectedSurface) -> QueryBundle:
        display = str(selected.term.surface["display_text"])
        concept_id = str(selected.term.concept["concept_id"])
        return QueryBundle(
            bundle_type="exploration",
            label=f"{display} exploration",
            queries=[
                QueryPlanQuery(
                    query_text=_quoted(display),
                    query_mode="exact",
                    surfaces=[display],
                    reason="Safe graph-backed term has unknown observed recall.",
                    priority=1,
                    source_concept_ids=[concept_id],
                    recall_bucket="unknown",
                )
            ],
            rationale="Exploration keeps emerging graph evidence visible.",
            priority=1,
            source_concept_ids=[concept_id],
            warnings=selected.warning_codes,
        )

    def _fallback_bundles(self, selection: SelectionResult) -> list[QueryBundle]:
        terms = list(selection.resolution.no_match_terms)
        rejected_norms = {
            rejection.normalized_surface for rejection in selection.rejected_surfaces
        }
        terms.extend(
            term
            for term in selection.resolution.matched_terms
            if term.normalized_surface in rejected_norms
        )
        if not terms:
            return []
        first = terms[0]
        warnings = ["fallback"]
        if first.normalized_surface in {
            term.normalized_surface for term in selection.resolution.no_match_terms
        }:
            warnings.insert(0, "no_match")
        return [
            QueryBundle(
                bundle_type="fallback",
                label=f"{first.text} fallback",
                queries=[
                    QueryPlanQuery(
                        query_text=_quoted(first.text),
                        query_mode="exact",
                        surfaces=[first.text],
                        reason="No trustworthy graph-backed route was available.",
                        priority=1,
                        source_concept_ids=[],
                        recall_bucket="unknown",
                    )
                ],
                rationale=(
                    "Fallback is included only because graph-backed planning found no "
                    "route."
                ),
                priority=1,
                source_concept_ids=[],
                warnings=warnings,
            )
        ]


def _quoted(text: str) -> str:
    return f'"{text}"'


def _strength_for_bundle(selection: SelectionResult, label: str) -> str:
    selected = _selected_for_label(selection, label)
    if selected is None:
        return "nice_to_have"
    return selected.term.strength


def _source_order_for_bundle(selection: SelectionResult, label: str) -> int:
    selected = _selected_for_label(selection, label)
    if selected is None:
        return 10_000
    return selected.term.source_order


def _quality_for_bundle(selection: SelectionResult, label: str) -> dict[str, float]:
    selected = _selected_for_label(selection, label)
    if selected is None:
        return {}
    return {
        "confidence": float(selected.term.confidence),
        "specificity_score": float(selected.term.surface["specificity_score"]),
        "ambiguity_score": float(selected.term.surface["ambiguity_score"]),
        "stability_score": float(selected.term.concept["stability_score"]),
    }


def _selected_for_label(
    selection: SelectionResult, label: str
) -> SelectedSurface | None:
    for selected in selection.selected:
        display = str(selected.term.surface["display_text"])
        if label.startswith(f"{display} "):
            return selected
    return None


def _dedupe_by_executable_query(bundles: list[QueryBundle]) -> list[QueryBundle]:
    deduped: list[QueryBundle] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for bundle in bundles:
        identity = tuple(
            (query.query_mode, query.query_text) for query in bundle.queries
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(bundle)
    return deduped
