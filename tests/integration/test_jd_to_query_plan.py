from __future__ import annotations

import sqlite3
from pathlib import Path

from _fixture_flow_loader import load_run_fixture_flow

from seektalent_keyword_graph.contracts import QueryPlanRequest
from seektalent_keyword_graph.engine import KeywordGraph

run_fixture_flow = load_run_fixture_flow()


def test_fixture_flow_builds_snapshot_and_all_query_bundle_types(
    tmp_path: Path,
) -> None:
    result = run_fixture_flow(tmp_path)

    assert result.build_db_path.is_file()
    assert result.snapshot_path.is_file()
    assert result.manifest_path.is_file()

    with sqlite3.connect(result.build_db_path) as conn:
        conn.row_factory = sqlite3.Row
        counts = {
            table: conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in (
                "jd_documents",
                "jd_sections",
                "keyword_mentions",
                "surfaces",
                "concepts",
                "surface_relations",
                "cooccurrence_edges",
                "provider_recall_observations",
            )
        }
        blocked_reasons = {
            row["reason_code"]
            for row in conn.execute(
                "select distinct reason_code from blocked_surface_candidates"
            )
        }

    assert counts["jd_documents"] == 3
    assert counts["jd_sections"] > 0
    assert counts["keyword_mentions"] > 0
    assert counts["surfaces"] > 0
    assert counts["concepts"] > 0
    assert counts["surface_relations"] > 0
    assert counts["cooccurrence_edges"] > 0
    assert counts["provider_recall_observations"] > 0
    assert {"company_like", "department_like"} <= blocked_reasons

    graph = KeywordGraph.open(result.snapshot_path, result.manifest_path)
    try:
        response = graph.build_query_plan(
            QueryPlanRequest(
                request_id="test-plan-bundles",
                requirement_terms=[
                    {"text": "Python 3", "strength": "required"},
                    {"text": "Kubernetes", "strength": "required"},
                    {"text": "React", "strength": "required"},
                    {"text": "Kafka", "strength": "preferred"},
                    {"text": "LLMOps", "strength": "preferred"},
                    {"text": "Acme Corp", "strength": "preferred"},
                    {"text": "Platform Team", "strength": "preferred"},
                ],
                max_query_bundles=10,
                include_exploration=True,
            )
        )

        fallback = graph.build_query_plan(
            QueryPlanRequest(
                request_id="test-plan-fallback",
                requirement_terms=[{"text": "CobolScript", "strength": "required"}],
                max_query_bundles=5,
            )
        )
    finally:
        graph.close()

    assert {bundle.bundle_type for bundle in response.query_bundles} == {
        "anchor",
        "precision",
        "alias_probe",
        "exploration",
    }
    assert [bundle.bundle_type for bundle in fallback.query_bundles] == ["fallback"]
    assert {
        rejection.reason_code for rejection in response.rejected_surfaces
    } >= {"company_like", "department_like"}
    assert response.lineage.input_hash.startswith("sha256:")
    assert all(response.lineage.source_refs)
