from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.runtime.bundle_builder import BundleBuilder
from seektalent_keyword_graph.runtime.concept_resolver import ConceptResolver
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.runtime.surface_selector import SurfaceSelector


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
        "precision",
        "alias_probe",
        "alias_probe",
        "exploration",
    ]
    assert [bundle.label for bundle in bundles] == [
        "Python anchor",
        "Kubernetes precision",
        "React alias probe",
        "Kafka alias probe",
        "LLMOps exploration",
    ]
    assert bundles[0].queries[0].query_text == '"Python"'
    assert bundles[1].queries[0].query_text == '"Kubernetes" "Docker"'
    assert bundles[2].queries[0].surfaces == ["React.js"]
    assert bundles[3].warnings == ["stale_observation"]
    assert bundles[4].warnings == ["unknown_observation"]


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
        "Kubernetes precision",
    ]
