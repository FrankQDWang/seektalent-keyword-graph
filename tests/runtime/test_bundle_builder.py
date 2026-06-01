from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.runtime.bundle_builder import BundleBuilder
from seektalent_keyword_graph.runtime.concept_resolver import (
    ConceptResolver,
    ResolvedInput,
    ResolvedTerm,
)
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.runtime.surface_selector import (
    SelectedSurface,
    SelectionResult,
    SurfaceSelector,
)


def test_bundle_builder_emits_real_bundle_types_in_deterministic_order(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-bundles",
        requirement_terms=[
            {"text": "Python", "strength": "required"},
            {"text": "Kubernetes", "strength": "required"},
            {"text": "React", "strength": "required"},
            {"text": "Kafka", "strength": "required"},
            {"text": "LLMOps", "strength": "preferred"},
        ],
        notes=["Docker"],
    )
    resolution = ConceptResolver(snapshot_store).resolve(request)
    selection = SurfaceSelector(snapshot_store).select(resolution)

    bundles = BundleBuilder().build(selection, max_query_bundles=10)

    assert [bundle.bundle_type for bundle in bundles] == [
        "anchor",
        "anchor",
        "precision",
        "alias_probe",
        "alias_probe",
        "exploration",
    ]
    assert [bundle.label for bundle in bundles] == [
        "Python anchor",
        "Docker anchor",
        "Kubernetes precision",
        "React alias probe",
        "Kafka alias probe",
        "LLMOps exploration",
    ]
    assert bundles[0].queries[0].query_text == '"Python"'
    assert bundles[1].queries[0].query_text == '"Docker"'
    assert bundles[2].queries[0].query_text == '"Kubernetes" "Docker"'
    assert bundles[3].queries[0].surfaces == ["React.js"]
    assert bundles[4].warnings == ["stale_observation"]
    assert bundles[5].warnings == ["unknown_observation"]


def test_bundle_builder_uses_fallback_only_without_trustworthy_graph_route(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    fallback_request = QueryPlanRequest(
        request_id="req-fallback",
        requirement_terms=[{"text": "GraphQL", "strength": "required"}],
    )
    fallback_resolution = ConceptResolver(snapshot_store).resolve(fallback_request)
    fallback_selection = SurfaceSelector(snapshot_store).select(fallback_resolution)

    fallback_bundles = BundleBuilder().build(fallback_selection, max_query_bundles=5)

    assert [bundle.bundle_type for bundle in fallback_bundles] == ["fallback"]
    assert fallback_bundles[0].queries[0].query_text == '"GraphQL"'
    assert fallback_bundles[0].warnings == ["no_match", "fallback"]

    graph_request = QueryPlanRequest(
        request_id="req-no-fallback",
        requirement_terms=[{"text": "Python", "strength": "required"}],
    )
    graph_resolution = ConceptResolver(snapshot_store).resolve(graph_request)
    graph_selection = SurfaceSelector(snapshot_store).select(graph_resolution)

    graph_bundles = BundleBuilder().build(graph_selection, max_query_bundles=5)

    assert [bundle.bundle_type for bundle in graph_bundles] == ["anchor"]


def test_bundle_builder_respects_max_query_bundles_after_sorting(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-max",
        requirement_terms=[
            {"text": "Python", "strength": "required"},
            {"text": "Kubernetes", "strength": "required"},
            {"text": "React", "strength": "required"},
            {"text": "Kafka", "strength": "required"},
            {"text": "LLMOps", "strength": "preferred"},
        ],
        notes=["Docker"],
        max_query_bundles=2,
    )
    resolution = ConceptResolver(snapshot_store).resolve(request)
    selection = SurfaceSelector(snapshot_store).select(resolution)

    bundles = BundleBuilder().build(
        selection, max_query_bundles=request.max_query_bundles
    )

    assert [bundle.label for bundle in bundles] == [
        "Python anchor",
        "Docker anchor",
    ]


def test_bundle_builder_falls_back_for_safe_matched_term_with_unsafe_graph_route(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-matched-fallback",
        requirement_terms=[{"text": "Terraform", "strength": "required"}],
    )
    resolution = ConceptResolver(snapshot_store).resolve(request)
    selection = SurfaceSelector(snapshot_store).select(resolution)

    bundles = BundleBuilder().build(selection, max_query_bundles=5)

    assert [bundle.bundle_type for bundle in bundles] == ["fallback"]
    assert bundles[0].queries[0].query_text == '"Terraform"'
    assert bundles[0].warnings == ["fallback"]


def test_bundle_builder_suppresses_duplicate_executable_queries(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-dedupe",
        requirement_terms=[
            {"text": "React", "strength": "required"},
            {"text": "React.js", "strength": "required"},
        ],
    )
    resolution = ConceptResolver(snapshot_store).resolve(request)
    selection = SurfaceSelector(snapshot_store).select(resolution)

    bundles = BundleBuilder().build(selection, max_query_bundles=10)

    assert [bundle.queries[0].query_text for bundle in bundles].count('"React.js"') == 1
    assert [bundle.label for bundle in bundles] == ["React.js anchor"]


def test_bundle_builder_uses_graph_quality_to_order_same_type_candidates() -> None:
    low_quality = _selected_anchor(
        text="Aaa Low Quality",
        concept_id="concept:low-quality",
        confidence=0.62,
        ambiguity_score=0.88,
        specificity_score=0.12,
        stability_score=0.62,
    )
    high_quality = _selected_anchor(
        text="Zzz High Quality",
        concept_id="concept:high-quality",
        confidence=0.97,
        ambiguity_score=0.08,
        specificity_score=0.94,
        stability_score=0.97,
    )
    request = QueryPlanRequest(
        request_id="req-quality-order",
        requirement_terms=[{"text": "Aaa Low Quality", "strength": "required"}],
    )
    resolution = ResolvedInput(
        request=request,
        matched_terms=[low_quality.term, high_quality.term],
        no_match_terms=[],
        rejected_surfaces=[],
        source_refs=[],
    )
    selection = SelectionResult(
        resolution=resolution,
        selected=[low_quality, high_quality],
        rejected_surfaces=[],
        warnings=[],
    )

    bundles = BundleBuilder().build(selection, max_query_bundles=1)

    assert [bundle.label for bundle in bundles] == ["Zzz High Quality anchor"]


def _selected_anchor(
    *,
    text: str,
    concept_id: str,
    confidence: float,
    ambiguity_score: float,
    specificity_score: float,
    stability_score: float,
) -> SelectedSurface:
    normalized = text.casefold()
    term = ResolvedTerm(
        text=text,
        normalized_surface=normalized,
        source="requirement",
        strength="required",
        source_order=0,
        surface={
            "surface_id": f"surface:{normalized.replace(' ', '-')}",
            "display_text": text,
            "text_norm": normalized,
            "recall_bucket": "healthy",
            "ambiguity_score": ambiguity_score,
            "specificity_score": specificity_score,
        },
        concept={
            "concept_id": concept_id,
            "canonical_label": text,
            "concept_type": "skill",
            "stability_score": stability_score,
        },
        confidence=confidence,
        source_ref=f"requirement:{normalized}",
    )
    return SelectedSurface(term=term, bundle_type="anchor")
