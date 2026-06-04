from __future__ import annotations

import json
from pathlib import Path

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.import_jds import import_jsonl_jds

FIXTURE = Path("tests/fixtures/jds/full_flow_jds.jsonl")


def test_jsonl_import_persists_stable_ids_hash_language_quality_and_events(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        report = import_jsonl_jds(store, FIXTURE, builder_run_id="run-import")
        first = store.get_jd_document("jd:06bcfb9c3f854bbf")
        second = store.get_jd_document("jd:1a670cdb9d0371c0")

        assert report.imported_count == 2
        assert report.duplicate_count == 1
        assert first is not None
        assert first["source_ref"] == "jd-python-ml"
        assert first["content_hash"] == (
            "sha256:06bcfb9c3f854bbf1a00538d0aef7602f834d689ab7df9babd11718207f26a3a"
        )
        assert first["language"] == "en"
        assert json.loads(str(first["quality_flags_json"])) == [
            "has_compensation",
            "has_location",
        ]
        assert second is not None
        assert second["language"] == "zh"
        assert json.loads(str(second["quality_flags_json"])) == [
            "has_compensation",
            "has_location",
        ]
        assert store.list_build_events("run-import")
    finally:
        store.close()


def test_jsonl_import_dedupes_duplicate_content_and_reports_bad_records(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        report = import_jsonl_jds(store, FIXTURE, builder_run_id="run-import")
        rows = store.connection.execute(
            "select source_ref from jd_documents order by source_ref"
        ).fetchall()

        assert [row[0] for row in rows] == ["jd-cn-frontend", "jd-python-ml"]
        assert report.duplicates == [
            {
                "line_number": 2,
                "source_ref": "jd-python-ml-copy",
                "duplicate_of_jd_id": "jd:06bcfb9c3f854bbf",
            }
        ]
        assert [error["reason"] for error in report.errors] == [
            "missing_text",
            "empty_text",
            "malformed_json",
        ]
        assert {error["line_number"] for error in report.errors} == {4, 5, 6}
    finally:
        store.close()


def test_jsonl_import_is_idempotent_for_same_builder_run(tmp_path: Path) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        first_report = import_jsonl_jds(store, FIXTURE, builder_run_id="run-import")
        second_report = import_jsonl_jds(store, FIXTURE, builder_run_id="run-import")
        events = store.list_build_events("run-import")

        assert first_report.imported_count == 2
        assert second_report.imported_count == 0
        assert second_report.duplicate_count == 3
        assert second_report.error_count == 3
        assert len(events) == 1
    finally:
        store.close()
