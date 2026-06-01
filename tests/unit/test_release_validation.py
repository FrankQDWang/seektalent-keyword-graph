from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.builder.build_snapshot import (
    BuildSnapshotConfig,
    build_runtime_snapshot,
)
from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.release_validation import validate_release_artifacts

NOW = "2026-06-01T00:00:00Z"


@pytest.fixture
def valid_artifacts(tmp_path: Path):
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


@pytest.mark.parametrize(
    ("column", "marker"),
    [
        ("display_text", "resume_text"),
        ("display_text", "candidate_id"),
        ("display_text", "candidate_list"),
        ("display_text", "KEYWORD_GRAPH_CTS_TENANT_SECRET"),
        ("display_text", "tenant_secret"),
    ],
)
def test_release_validation_rejects_privacy_and_secret_markers(
    valid_artifacts, column: str, marker: str
) -> None:
    conn = sqlite3.connect(valid_artifacts.snapshot_path)
    try:
        conn.execute(f"update surfaces set {column} = ?", (marker,))
        conn.commit()
    finally:
        conn.close()

    result = validate_release_artifacts(
        valid_artifacts.snapshot_path,
        valid_artifacts.manifest_path,
        compressed_snapshot_path=valid_artifacts.compressed_snapshot_path,
    )

    assert not result.ok
    assert any(marker.lower() in error.message.lower() for error in result.errors)


def test_release_validation_rejects_referential_integrity_failures(
    valid_artifacts,
) -> None:
    conn = sqlite3.connect(valid_artifacts.snapshot_path)
    try:
        conn.execute("pragma foreign_keys = off")
        conn.execute(
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            )
            values('missing-concept', 'surface-1', 0.7, 'test', 'active')
            """
        )
        conn.commit()
    finally:
        conn.close()

    result = validate_release_artifacts(
        valid_artifacts.snapshot_path,
        valid_artifacts.manifest_path,
        compressed_snapshot_path=valid_artifacts.compressed_snapshot_path,
    )

    assert not result.ok
    assert any("orphan reference" in error.message for error in result.errors)


def test_release_validation_rejects_serving_surface_without_valid_policy_observation(
    valid_artifacts,
) -> None:
    conn = sqlite3.connect(valid_artifacts.snapshot_path)
    try:
        conn.execute("delete from cts_recall_observations")
        conn.execute(
            "update surfaces set recall_bucket = 'unknown' "
            "where surface_id = 'surface-1'"
        )
        conn.commit()
    finally:
        conn.close()

    result = validate_release_artifacts(
        valid_artifacts.snapshot_path,
        valid_artifacts.manifest_path,
        compressed_snapshot_path=valid_artifacts.compressed_snapshot_path,
    )

    assert not result.ok
    assert any("valid recall observation" in error.message for error in result.errors)
