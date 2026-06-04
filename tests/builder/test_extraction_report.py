from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.extract_surfaces import extract_surfaces
from seektalent_keyword_graph.builder.import_jds import import_jsonl_jds
from seektalent_keyword_graph.observability.build_report import (
    generate_extraction_report,
)

FIXTURE = Path("tests/fixtures/jds/full_flow_jds.jsonl")


def test_extraction_report_includes_counts_top_surfaces_blocked_and_failures(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_report = import_jsonl_jds(store, FIXTURE, builder_run_id="run-report")
        extract_surfaces(store, builder_run_id="run-report")

        report = generate_extraction_report(store, import_report=import_report)

        assert report["counts"] == {
            "jd_documents": 2,
            "jd_sections": 11,
            "keyword_mentions": 15,
            "surfaces": 14,
            "blocked_candidates": 11,
            "import_errors": 3,
            "duplicates": 1,
        }
        assert report["top_surfaces"][:3] == [
            {
                "text_norm": "kubernetes",
                "display_text": "Kubernetes",
                "jd_df": 2,
                "jd_tf_total": 2,
            },
            {
                "text_norm": "aws certified solutions architect",
                "display_text": "AWS Certified Solutions Architect",
                "jd_df": 1,
                "jd_tf_total": 1,
            },
            {
                "text_norm": "docker",
                "display_text": "Docker",
                "jd_df": 1,
                "jd_tf_total": 1,
            },
        ]
        assert report["blocked_reason_summary"] == {
            "company_like": 2,
            "department_like": 2,
            "policy_blocked": 5,
            "too_generic": 2,
        }
        assert [record["reason"] for record in report["failed_records"]] == [
            "missing_text",
            "empty_text",
            "malformed_json",
        ]
    finally:
        store.close()
