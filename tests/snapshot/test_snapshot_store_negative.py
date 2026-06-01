from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.runtime.errors import (
    SnapshotChecksumError,
    SnapshotFormatError,
    SnapshotPrivacyError,
    SnapshotSchemaError,
    UnsupportedSnapshotVersionError,
)
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.sqlite_migrations import migrate_runtime_snapshot
from seektalent_keyword_graph.storage.sqlite_schema import REQUIRED_SNAPSHOT_META_KEYS


def make_snapshot(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        migrate_runtime_snapshot(conn)
        conn.executemany(
            "insert into snapshot_meta(key, value) values (?, ?)",
            [(key, f"{key}-value") for key in REQUIRED_SNAPSHOT_META_KEYS],
        )
        conn.execute(
            "update snapshot_meta set value = ? where key = ?",
            ("snapshot-v1", "snapshot_schema_version"),
        )
        conn.execute(
            "update snapshot_meta set value = ? where key = ?",
            ("policy-v1", "selection_policy_version"),
        )
        conn.execute(
            "insert or replace into snapshot_meta(key, value) values (?, ?)",
            ("provider_sources", '["cts"]'),
        )
        conn.commit()
    finally:
        conn.close()


def test_missing_required_table_fails_with_typed_error(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("drop table selection_policy_meta")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="selection_policy_meta"):
        SQLiteSnapshotStore.open(path)


def test_missing_provider_observation_table_fails_with_typed_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("drop table provider_recall_observations")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="provider_recall_observations"):
        SQLiteSnapshotStore.open(path)


def test_missing_provider_observation_index_fails_with_typed_error(
    tmp_path: Path,
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("drop index idx_snapshot_provider_observations_query_observed")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(
        SnapshotSchemaError, match="idx_snapshot_provider_observations_query_observed"
    ):
        SQLiteSnapshotStore.open(path)


def test_missing_required_meta_key_fails_with_typed_error(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("delete from snapshot_meta where key = ?", ("manifest_sha256",))
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="manifest_sha256"):
        SQLiteSnapshotStore.open(path)


def test_unsupported_snapshot_version_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "update snapshot_meta set value = ? where key = ?",
            ("snapshot-v2", "snapshot_schema_version"),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(UnsupportedSnapshotVersionError, match="snapshot-v2"):
        SQLiteSnapshotStore.open(path)


@pytest.mark.parametrize("payload", [b"not sqlite", b"SQLite format 3\x00corrupt"])
def test_non_sqlite_and_corrupt_files_fail(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "bad.sqlite3"
    path.write_bytes(payload)

    with pytest.raises(SnapshotFormatError):
        SQLiteSnapshotStore.open(path)


def test_privacy_marker_in_snapshot_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "insert into surfaces(surface_id, text_raw, text_norm, display_text, "
            "language, token_class, query_safe, is_exact_phrase_preferred, "
            "ambiguity_score, specificity_score, jd_df, jd_tf_total, recall_bucket, "
            "serving_status, created_at, updated_at) values "
            "('s1', 'resume_text', 'resume_text', 'resume_text', 'en', 'skill', 1, 0, "
            "0.1, 0.9, 1, 1, 'unknown', 'active', 'now', 'now')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotPrivacyError, match="resume_text"):
        SQLiteSnapshotStore.open(path)


def test_privacy_marker_in_provider_observation_query_text_fails(
    tmp_path: Path,
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "insert into surfaces(surface_id, text_raw, text_norm, display_text, "
            "language, token_class, query_safe, is_exact_phrase_preferred, "
            "ambiguity_score, specificity_score, jd_df, jd_tf_total, recall_bucket, "
            "serving_status, created_at, updated_at) values "
            "('s1', 'Python', 'python', 'Python', 'en', 'skill', 1, 0, "
            "0.1, 0.9, 1, 1, 'healthy', 'active', 'now', 'now')"
        )
        conn.execute(
            "insert into provider_recall_observations("
            "observation_id, provider, surface_id, query_text, query_hash, query_mode, "
            "total, latency_ms, status, error_code, observed_at, recall_bucket, "
            "provider_api_version, builder_run_id, evidence_ref) values "
            "('obs-1', 'cts', 's1', 'candidate_id', 'hash', 'keyword', "
            "1, 1, 'ok', null, 'now', 'healthy', 'fake-v1', 'run-1', 'probe:obs-1')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotPrivacyError, match="candidate_id"):
        SQLiteSnapshotStore.open(path)


def test_serving_surface_without_provider_observation_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "insert into surfaces(surface_id, text_raw, text_norm, display_text, "
            "language, token_class, query_safe, is_exact_phrase_preferred, "
            "ambiguity_score, specificity_score, jd_df, jd_tf_total, recall_bucket, "
            "serving_status, created_at, updated_at) values "
            "('s1', 'Python', 'python', 'Python', 'en', 'skill', 1, 0, "
            "0.1, 0.9, 1, 1, 'healthy', 'active', 'now', 'now')"
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="provider recall observation"):
        SQLiteSnapshotStore.open(path)


def test_orphan_concept_primary_surface_id_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            insert into concepts(
              concept_id, canonical_label, concept_type, description,
              primary_surface_id, surface_count, jd_df, stability_score,
              review_status, created_at, updated_at
            ) values (
              'concept-1', 'Python', 'language', 'Python language', 'missing-surface',
              1, 1, 0.9, 'approved', 'now', 'now'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="concepts.primary_surface_id"):
        SQLiteSnapshotStore.open(path)


@pytest.mark.parametrize(
    ("sql", "expected_match"),
    [
        (
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            ) values ('missing-concept', 'surface-1', 0.9, 'test', 'active')
            """,
            "concept_surfaces.concept_id",
        ),
        (
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            ) values ('concept-1', 'missing-surface', 0.9, 'test', 'active')
            """,
            "concept_surfaces.surface_id",
        ),
    ],
)
def test_orphan_concept_surface_links_fail(
    tmp_path: Path, sql: str, expected_match: str
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "insert into surfaces(surface_id, text_raw, text_norm, display_text, "
            "language, token_class, query_safe, is_exact_phrase_preferred, "
            "ambiguity_score, specificity_score, jd_df, jd_tf_total, recall_bucket, "
            "serving_status, created_at, updated_at) values "
            "('surface-1', 'Python', 'python', 'Python', 'en', 'skill', 1, 0, "
            "0.1, 0.9, 1, 1, 'healthy', 'active', 'now', 'now')"
        )
        conn.execute(
            """
            insert into concepts(
              concept_id, canonical_label, concept_type, description,
              primary_surface_id, surface_count, jd_df, stability_score,
              review_status, created_at, updated_at
            ) values (
              'concept-1', 'Python', 'language', 'Python language', 'surface-1',
              1, 1, 0.9, 'approved', 'now', 'now'
            )
            """
        )
        conn.execute(sql)
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match=expected_match):
        SQLiteSnapshotStore.open(path)


def test_manifest_checksum_mismatch_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {"snapshot": path.name},
                "sha256": {"snapshot": "0" * 64},
                "byte_sizes": {"snapshot": path.stat().st_size},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SnapshotChecksumError, match="sha256"):
        SQLiteSnapshotStore.open(path, manifest)


@pytest.mark.parametrize(
    "manifest_payload",
    [
        [],
        {"artifacts": [], "sha256": {}, "byte_sizes": {}},
    ],
)
def test_invalid_manifest_shape_fails_with_typed_error(
    tmp_path: Path, manifest_payload: object
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")

    with pytest.raises(SnapshotChecksumError):
        SQLiteSnapshotStore.open(path, manifest)


def test_opening_runtime_snapshot_does_not_read_cts_env_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    monkeypatch.setenv("KEYWORD_GRAPH_CTS_TENANT_SECRET", "do-not-read")
    original_getenv = os.getenv

    def guarded_getenv(key: str, default: str | None = None) -> str | None:
        if key.startswith("KEYWORD_GRAPH_CTS_"):
            raise AssertionError(f"runtime read forbidden CTS env var {key}")
        return original_getenv(key, default)

    monkeypatch.setattr(os, "getenv", guarded_getenv)

    store = SQLiteSnapshotStore.open(path)
    store.close()
