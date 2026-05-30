from pathlib import Path

from seektalent_keyword_graph import KeywordGraph, QueryPlanRequest

FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")


def test_build_query_plan_returns_anchor_for_known_term():
    graph = KeywordGraph.open(FIXTURE)
    request = QueryPlanRequest(
        request_id="req_001",
        seek_talent_run_id="run_001",
        job_title="Platform engineer",
        jd_text="Need k8s experience.",
        requirement_terms=[{"text": "k8s", "strength": "required"}],
    )

    response = graph.build_query_plan(request)

    assert response.request_id == "req_001"
    assert response.kg_snapshot_id == "kg_fixture"
    assert response.query_bundles[0].bundle_type == "anchor"
    assert response.query_bundles[0].queries[0].query_text == "k8s"


def test_build_query_plan_fallback_for_unknown_term():
    graph = KeywordGraph.open(FIXTURE)
    request = QueryPlanRequest(
        request_id="req_002",
        seek_talent_run_id="run_001",
        job_title="Unknown role",
        jd_text="Need something rare.",
        requirement_terms=[{"text": "rareterm", "strength": "required"}],
    )

    response = graph.build_query_plan(request)

    assert response.query_bundles[0].bundle_type == "fallback"
    assert response.warnings[0].code == "no_snapshot_surface_match"
