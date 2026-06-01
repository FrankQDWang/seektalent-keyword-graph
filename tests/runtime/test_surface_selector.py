from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.runtime.concept_resolver import ConceptResolver
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.runtime.surface_selector import SurfaceSelector


def test_surface_selector_assigns_bundle_routes_and_warnings(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-selector",
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

    by_norm = {selected.normalized_surface: selected for selected in selection.selected}
    assert by_norm["python"].bundle_type == "anchor"
    assert by_norm["kubernetes"].bundle_type == "precision"
    assert by_norm["kubernetes"].companions[0].normalized_surface == "docker"
    assert by_norm["react"].bundle_type == "alias_probe"
    assert by_norm["react"].aliases[0].normalized_surface == "react.js"
    assert by_norm["kafka"].bundle_type == "alias_probe"
    assert by_norm["kafka"].aliases[0].normalized_surface == "apache kafka"
    assert by_norm["llmops"].bundle_type == "exploration"
    assert [(warning.code, warning.source_terms) for warning in selection.warnings] == [
        ("stale_observation", ["Kafka"]),
        ("unknown_observation", ["LLMOps"]),
    ]


def test_surface_selector_rejects_too_wide_without_companion(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-too-wide",
        requirement_terms=[{"text": "Kubernetes", "strength": "required"}],
    )
    resolution = ConceptResolver(snapshot_store).resolve(request)

    selection = SurfaceSelector(snapshot_store).select(resolution)

    assert selection.selected == []
    assert [
        (rejection.normalized_surface, rejection.reason_code)
        for rejection in selection.rejected_surfaces
    ] == [("kubernetes", "too_wide_without_companion")]
