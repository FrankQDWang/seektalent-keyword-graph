from __future__ import annotations

import sqlite3
from pathlib import Path

from seektalent_keyword_graph.builder.build_snapshot import (
    BuildSnapshotConfig,
    build_runtime_snapshot,
)
from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.validate_snapshot import validate_snapshot

NOW = "2026-06-01T00:00:00Z"


def make_valid_snapshot(tmp_path: Path):
    build_db = tmp_path / "build.sqlite3"
    store = BuildStore.open(build_db)
    try:
        store.insert_builder_run(
            builder_run_id="run-1",
            started_at="2026-05-31T23:00:00Z",
            finished_at=NOW,
            input_corpus_version="corpus-1",
            status="succeeded",
            report_json="{}",
        )
        store.insert_surface(
            surface_id="surface-1",
            text_raw="Python",
            text_norm="python",
            display_text="Python",
            language="en",
            token_class="skill",
            query_safe=True,
            is_exact_phrase_preferred=False,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=5,
            jd_tf_total=8,
            serving_status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        store.insert_probe_job(
            probe_job_id="probe-1",
            surface_id="surface-1",
            query_text="Python",
            query_mode="keyword",
            priority=1,
            dedupe_key="python:keyword",
            scheduled_at=NOW,
            not_before=NOW,
            attempt_count=0,
            status="succeeded",
            rate_limit_bucket="fake",
            created_reason="release",
            last_error_code=None,
        )
        store.insert_cts_recall_observation(
            observation_id="obs-1",
            probe_job_id="probe-1",
            surface_id="surface-1",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            total=42,
            latency_ms=12,
            status="ok",
            error_code=None,
            observed_at="2026-05-31T23:55:00Z",
            cts_api_version="fake-v1",
            builder_run_id="run-1",
        )
    finally:
        store.close()

    return build_runtime_snapshot(
        build_db,
        tmp_path / "out",
        BuildSnapshotConfig(
            kg_snapshot_id="kg-snapshot-test",
            built_at=NOW,
            source_corpus_version="corpus-1",
            builder_run_id="run-1",
            cts_probe_window_start="2026-05-31T00:00:00Z",
            cts_probe_window_end=NOW,
        ),
    )


def test_validate_snapshot_accepts_complete_artifact_set(tmp_path: Path) -> None:
    result = make_valid_snapshot(tmp_path)

    validation = validate_snapshot(
        result.snapshot_path,
        result.manifest_path,
        compressed_snapshot_path=result.compressed_snapshot_path,
    )

    assert validation.ok
    assert validation.snapshot_sha256
    assert validation.gzip_size_bytes == result.compressed_snapshot_path.stat().st_size


def test_validate_snapshot_rejects_changed_snapshot_bytes(tmp_path: Path) -> None:
    result = make_valid_snapshot(tmp_path)
    conn = sqlite3.connect(result.snapshot_path)
    try:
        conn.execute(
            "insert into selection_policy_meta(key, value) values('tampered', 'yes')"
        )
        conn.commit()
    finally:
        conn.close()

    validation = validate_snapshot(
        result.snapshot_path,
        result.manifest_path,
        compressed_snapshot_path=result.compressed_snapshot_path,
    )

    assert not validation.ok
    assert any("sha256 mismatch" in error.message for error in validation.errors)


def test_validate_snapshot_rejects_oversized_compressed_artifact(
    tmp_path: Path,
) -> None:
    result = make_valid_snapshot(tmp_path)

    validation = validate_snapshot(
        result.snapshot_path,
        result.manifest_path,
        compressed_snapshot_path=result.compressed_snapshot_path,
        max_gzip_bytes=result.compressed_snapshot_path.stat().st_size - 1,
    )

    assert not validation.ok
    assert any(
        "compressed snapshot exceeds" in error.message for error in validation.errors
    )
