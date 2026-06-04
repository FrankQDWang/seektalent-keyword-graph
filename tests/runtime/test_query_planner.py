from __future__ import annotations

import os

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.engine import KeywordGraph
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore


def test_query_planner_response_is_deterministic_and_has_lineage(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-plan",
        requirement_terms=[
            {"text": "Python", "strength": "required"},
            {"text": "Kubernetes", "strength": "required"},
            {"text": "React", "strength": "required"},
            {"text": "Kafka", "strength": "required"},
            {"text": "LLMOps", "strength": "preferred"},
            {"text": "GraphQL", "strength": "preferred"},
        ],
        title="Senior Python engineer",
        jd_text="Build Vector Search services with Kubernetes.",
        notes=["Docker", "React migration", "Kafka operations"],
        max_query_bundles=4,
    )

    first = KeywordGraph(snapshot_store).build_query_plan(request)
    second = KeywordGraph(snapshot_store).build_query_plan(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.schema_version == "query-plan-response-v1"
    assert first.kg_snapshot_id == "kg-test-snapshot"
    assert first.selection_policy_version == "policy-v1"
    assert [bundle.bundle_type for bundle in first.query_bundles] == [
        "anchor",
        "anchor",
        "anchor",
        "precision",
    ]
    assert len(first.query_bundles) == 4
    assert first.lineage.input_hash.startswith("sha256:")
    assert first.lineage.snapshot_schema_version == "snapshot-v1"
    assert first.lineage.selection_policy_version == "policy-v1"
    assert first.lineage.source_refs == [
        "request:req-plan",
        "snapshot:kg-test-snapshot",
        "requirement:python",
        "requirement:kubernetes",
        "requirement:react",
        "requirement:kafka",
        "requirement:llmops",
        "requirement:graphql",
        "title:python",
        "jd_text:vector search",
        "jd_text:kubernetes",
        "notes:docker",
        "notes:react",
        "notes:kafka",
    ]


def test_query_planner_includes_warning_codes_and_rejections(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-warnings",
        requirement_terms=[
            {"text": "Acme AI", "strength": "required"},
            {"text": "Kafka", "strength": "required"},
            {"text": "LLMOps", "strength": "preferred"},
            {"text": "GraphQL", "strength": "preferred"},
        ],
        max_query_bundles=5,
    )

    response = KeywordGraph(snapshot_store).build_query_plan(request)

    assert [(warning.code, warning.source_terms) for warning in response.warnings] == [
        ("no_match", ["GraphQL"]),
        ("stale_observation", ["Kafka"]),
        ("unknown_observation", ["LLMOps"]),
    ]
    assert [
        (rejection.normalized_surface, rejection.reason_code)
        for rejection in response.rejected_surfaces
    ] == [("acme ai", "company_like")]


def test_query_planner_warns_when_fallback_is_used(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-fallback-warning",
        requirement_terms=[{"text": "GraphQL", "strength": "required"}],
    )

    response = KeywordGraph(snapshot_store).build_query_plan(request)

    assert [bundle.bundle_type for bundle in response.query_bundles] == ["fallback"]
    assert [(warning.code, warning.source_terms) for warning in response.warnings] == [
        ("no_match", ["GraphQL"]),
        ("fallback", ["GraphQL"]),
    ]


def test_query_planner_warns_when_fallback_uses_safe_matched_term(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-safe-matched-fallback",
        requirement_terms=[{"text": "Terraform", "strength": "required"}],
    )

    response = KeywordGraph(snapshot_store).build_query_plan(request)

    assert [bundle.bundle_type for bundle in response.query_bundles] == ["fallback"]
    assert response.query_bundles[0].queries[0].query_text == '"Terraform"'
    assert [(warning.code, warning.source_terms) for warning in response.warnings] == [
        ("fallback", ["Terraform"])
    ]


def test_query_planner_honors_include_exploration_false(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryPlanRequest(
        request_id="req-no-exploration",
        requirement_terms=[{"text": "LLMOps", "strength": "required"}],
        include_exploration=False,
    )

    response = KeywordGraph(snapshot_store).build_query_plan(request)

    assert [bundle.bundle_type for bundle in response.query_bundles] == ["fallback"]
    assert response.query_bundles[0].queries[0].query_text == '"LLMOps"'
    assert all(bundle.bundle_type != "exploration" for bundle in response.query_bundles)
    assert "unknown_observation" not in {warning.code for warning in response.warnings}


def test_keyword_graph_open_and_planning_do_not_read_cts_env_vars(
    snapshot_store: SQLiteSnapshotStore, monkeypatch
) -> None:
    snapshot_path = snapshot_store.path
    monkeypatch.setenv("KEYWORD_GRAPH_CTS_TENANT_SECRET", "do-not-read")
    original_getenv = os.getenv

    def guarded_getenv(key: str, default: str | None = None) -> str | None:
        if key.startswith("KEYWORD_GRAPH_CTS_"):
            raise AssertionError(f"runtime read forbidden CTS env var {key}")
        return original_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)

    graph = KeywordGraph.open(snapshot_path)
    try:
        response = graph.build_query_plan(
            QueryPlanRequest(
                request_id="req-env",
                requirement_terms=[{"text": "Python", "strength": "required"}],
            )
        )
    finally:
        graph.close()

    assert [bundle.bundle_type for bundle in response.query_bundles] == ["anchor"]
