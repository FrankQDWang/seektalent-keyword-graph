from __future__ import annotations

import json
from pathlib import Path

from _fixture_flow_loader import load_run_fixture_flow

run_fixture_flow = load_run_fixture_flow()


def test_replay_report_summarizes_fixture_flow_and_is_stable(
    tmp_path: Path,
) -> None:
    first = run_fixture_flow(tmp_path / "first")
    second = run_fixture_flow(tmp_path / "second")

    first_report = json.loads(first.replay_report_path.read_text(encoding="utf-8"))
    second_report = json.loads(second.replay_report_path.read_text(encoding="utf-8"))

    assert first_report == second_report

    summary = first_report["summary"]
    assert summary["case_count"] == 6
    assert summary["bundle_type_counts"] == {
        "alias_probe": 2,
        "anchor": 1,
        "exploration": 1,
        "fallback": 1,
        "precision": 1,
    }
    assert summary["warning_counts"] == {
        "fallback": 2,
        "matched_without_observation": 1,
        "no_match": 2,
        "stale_observation": 2,
        "too_narrow_recall": 1,
        "too_wide_recall": 2,
        "unknown_observation": 3,
        "zero_recall": 2,
    }
    assert summary["rejected_reason_counts"] == {
        "company_like": 1,
        "department_like": 1,
    }
    assert summary["query_recall_action_counts"] == {
        "add_precision_companion": 2,
        "fallback": 1,
        "keep": 3,
        "replace": 3,
        "score_only": 3,
    }
    assert summary["provider_observation_status_counts"] == {
        "ok": 9,
        "unknown": 1,
    }

    assert first_report["provider_recall_summary"] == {
        "boss": {"healthy": 21, "too_wide": 1, "zero": 1},
        "cts": {"healthy": 19, "stale": 1, "too_wide": 1, "unknown": 1, "zero": 1},
        "liepin": {"healthy": 21, "too_narrow": 1, "zero": 1},
    }
    assert first_report["stability"]["stable_case_ids"] == [
        "plan-fallback-only",
        "plan-full-bundle-matrix",
        "recall-boss-provider",
        "recall-cts-term-pool",
        "recall-liepin-provider",
        "recall-phrase-without-observation",
    ]

    for case in first_report["cases"]:
        assert case["lineage"]["input_hash"].startswith("sha256:")
        assert case["lineage"]["source_refs"]
