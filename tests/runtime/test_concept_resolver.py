from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.runtime.concept_resolver import ConceptResolver
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore


def test_concept_resolution_uses_requirement_title_jd_text_and_notes(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-resolution",
        requirement_terms=[{"text": "Kubernetes", "strength": "required"}],
        title="Senior Python engineer",
        jd_text="Build Vector Search services.",
        notes=["Need Kafka operations"],
    )

    resolution = ConceptResolver(snapshot_store).resolve(request)

    by_norm = {term.normalized_surface: term for term in resolution.matched_terms}
    assert by_norm["kubernetes"].source == "requirement"
    assert by_norm["python"].source == "title"
    assert by_norm["vector search"].source == "jd_text"
    assert by_norm["kafka"].source == "notes"
    assert [term.concept["concept_id"] for term in resolution.matched_terms] == [
        "concept:kubernetes",
        "concept:python",
        "concept:vector-search",
        "concept:kafka",
    ]


def test_concept_resolution_rejects_company_department_and_generic_terms(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-rejections",
        requirement_terms=[
            {"text": "Acme AI", "strength": "required"},
            {"text": "Platform Engineering", "strength": "required"},
            {"text": "Familiar", "strength": "preferred"},
        ],
    )

    resolution = ConceptResolver(snapshot_store).resolve(request)

    rejected = {
        rejection.normalized_surface: rejection.reason_code
        for rejection in resolution.rejected_surfaces
    }
    assert rejected == {
        "acme ai": "company_like",
        "platform engineering": "department_like",
        "familiar": "too_generic",
    }
    assert resolution.matched_terms == []


def test_concept_resolution_records_safe_no_match_terms(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-no-match",
        requirement_terms=[{"text": "GraphQL", "strength": "required"}],
    )

    resolution = ConceptResolver(snapshot_store).resolve(request)

    assert [
        (term.text, term.normalized_surface) for term in resolution.no_match_terms
    ] == [("GraphQL", "graphql")]
    assert resolution.rejected_surfaces == []
