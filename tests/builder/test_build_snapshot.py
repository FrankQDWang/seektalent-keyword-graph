from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

from seektalent_keyword_graph.builder.build_snapshot import (
    BuildSnapshotConfig,
    build_runtime_snapshot,
)
from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.sqlite_schema import (
    REQUIRED_SNAPSHOT_META_KEYS,
    SNAPSHOT_INDEXES,
    SNAPSHOT_TABLES,
)

NOW = "2026-06-01T00:00:00Z"


def seed_build_db(path: Path) -> None:
    store = BuildStore.open(path)
    try:
        store.insert_builder_run(
            builder_run_id="run-1",
            started_at="2026-05-31T23:00:00Z",
            finished_at=NOW,
            input_corpus_version="corpus-2026-06-01",
            status="succeeded",
            report_json="{}",
        )
        store.insert_surface(
            surface_id="surface-python",
            text_raw="Python",
            text_norm="python",
            display_text="Python",
            language="en",
            token_class="skill",
            query_safe=True,
            is_exact_phrase_preferred=False,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=12,
            jd_tf_total=34,
            serving_status="active",
            created_at="2026-05-31T00:00:00Z",
            updated_at="2026-05-31T00:00:00Z",
        )
        store.insert_surface(
            surface_id="surface-sql",
            text_raw="SQL",
            text_norm="sql",
            display_text="SQL",
            language="en",
            token_class="skill",
            query_safe=True,
            is_exact_phrase_preferred=True,
            ambiguity_score=0.2,
            specificity_score=0.8,
            jd_df=8,
            jd_tf_total=15,
            serving_status="inactive",
            created_at="2026-05-31T00:00:00Z",
            updated_at="2026-05-31T00:00:00Z",
        )
        store.insert_concept(
            concept_id="concept-python",
            canonical_label="Python",
            concept_type="language",
            description="Python programming language",
            primary_surface_id="surface-python",
            surface_count=1,
            jd_df=12,
            stability_score=0.91,
            review_status="approved",
            created_at="2026-05-31T00:00:00Z",
            updated_at="2026-05-31T00:00:00Z",
        )
        store.insert_concept_surface(
            concept_id="concept-python",
            surface_id="surface-python",
            confidence=0.95,
            source="clusterer",
            status="active",
        )
        store.insert_surface_relation(
            relation_id="relation-python-sql",
            from_surface_id="surface-python",
            to_surface_id="surface-sql",
            relation_type="related",
            confidence=0.72,
            evidence_type="cooccurrence",
            created_by="builder",
            status="active",
        )
        store.insert_cooccurrence_edge(
            edge_id="edge-python-sql",
            surface_id_a="surface-python",
            surface_id_b="surface-sql",
            window_type="jd",
            cooccur_count=7,
            pmi=1.2,
            jaccard=0.4,
            support=0.35,
            last_computed_at=NOW,
        )
        store.insert_probe_job(
            probe_job_id="probe-python",
            surface_id="surface-python",
            query_text="Python",
            query_mode="keyword",
            priority=1,
            dedupe_key="python:keyword",
            scheduled_at="2026-05-31T00:00:00Z",
            not_before="2026-05-31T00:00:00Z",
            attempt_count=0,
            status="succeeded",
            rate_limit_bucket="fake",
            created_reason="release",
            last_error_code=None,
        )
        store.insert_cts_recall_observation(
            observation_id="obs-python-ok",
            probe_job_id="probe-python",
            surface_id="surface-python",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            total=42,
            latency_ms=15,
            status="ok",
            error_code=None,
            observed_at="2026-05-31T23:50:00Z",
            cts_api_version="fake-v1",
            builder_run_id="run-1",
        )
        store.insert_cts_recall_observation(
            observation_id="obs-python-later-fail",
            probe_job_id="probe-python",
            surface_id="surface-python",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            total=None,
            latency_ms=None,
            status="error",
            error_code="timeout",
            observed_at="2026-05-31T23:59:00Z",
            cts_api_version="fake-v1",
            builder_run_id="run-1",
        )
    finally:
        store.close()


def sqlite_object_names(conn: sqlite3.Connection, object_type: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master "
            "where type = ? and name not like 'sqlite_%'",
            (object_type,),
        )
    }


def test_build_snapshot_projects_release_safe_runtime_artifacts(
    tmp_path: Path,
) -> None:
    build_db = tmp_path / "build.sqlite3"
    seed_build_db(build_db)

    result = build_runtime_snapshot(
        build_db,
        tmp_path / "out",
        BuildSnapshotConfig(
            kg_snapshot_id="kg-snapshot-test",
            built_at=NOW,
            source_corpus_version="corpus-2026-06-01",
            builder_run_id="run-1",
            cts_probe_window_start="2026-05-31T00:00:00Z",
            cts_probe_window_end=NOW,
        ),
    )

    assert result.snapshot_path.is_file()
    assert result.manifest_path.is_file()
    assert result.compressed_snapshot_path.is_file()
    assert result.build_report_path.is_file()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["artifacts"] == {
        "sqlite": result.snapshot_path.name,
        "sqlite_gzip": result.compressed_snapshot_path.name,
    }
    assert manifest["sha256"]["sqlite"] == hashlib.sha256(
        result.snapshot_path.read_bytes()
    ).hexdigest()
    assert manifest["byte_sizes"]["sqlite"] == result.snapshot_path.stat().st_size
    assert gzip.decompress(result.compressed_snapshot_path.read_bytes()) == (
        result.snapshot_path.read_bytes()
    )

    conn = sqlite3.connect(result.snapshot_path)
    try:
        assert sqlite_object_names(conn, "table") >= SNAPSHOT_TABLES
        assert sqlite_object_names(conn, "index") >= SNAPSHOT_INDEXES
        meta = dict(conn.execute("select key, value from snapshot_meta").fetchall())
        assert set(meta) >= REQUIRED_SNAPSHOT_META_KEYS
        assert meta["kg_snapshot_id"] == "kg-snapshot-test"

        observations = conn.execute(
            "select observation_id, total, status from cts_recall_observations"
        ).fetchall()
        assert observations == [("obs-python-ok", 42, "ok")]
        assert conn.execute(
            "select recall_bucket from surfaces where surface_id = 'surface-python'"
        ).fetchone() == ("healthy",)
        assert conn.execute("select count(*) from concepts").fetchone() == (1,)
        assert conn.execute("select count(*) from surfaces").fetchone() == (2,)
        assert conn.execute("select count(*) from surface_relations").fetchone() == (1,)
        cooccurrence_count = conn.execute(
            "select count(*) from cooccurrence_edges"
        ).fetchone()
        assert cooccurrence_count == (1,)
        assert conn.execute(
            "select count(*) from sqlite_master where name in "
            "('jd_documents', 'keyword_mentions', 'probe_jobs')"
        ).fetchone() == (0,)
    finally:
        conn.close()

    store = SQLiteSnapshotStore.open(result.snapshot_path, result.manifest_path)
    store.close()
