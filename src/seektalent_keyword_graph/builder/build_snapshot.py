"""Build deterministic releaseable runtime snapshots from the build database."""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from seektalent_keyword_graph import __version__
from seektalent_keyword_graph.contracts.snapshot import SnapshotManifest
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.sqlite_migrations import migrate_runtime_snapshot
from seektalent_keyword_graph.storage.sqlite_schema import (
    SELECTION_POLICY_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
)


@dataclass(frozen=True)
class BuildSnapshotConfig:
    """Explicit metadata and policy knobs for a snapshot build."""

    kg_snapshot_id: str
    built_at: str
    source_corpus_version: str
    builder_run_id: str
    cts_probe_window_start: str
    cts_probe_window_end: str
    max_observation_age_days: int = 7
    healthy_min_total: int = 10
    healthy_max_total: int = 1000


@dataclass(frozen=True)
class BuildSnapshotResult:
    """Paths emitted by a snapshot build."""

    snapshot_path: Path
    manifest_path: Path
    compressed_snapshot_path: Path
    build_report_path: Path


def build_runtime_snapshot(
    build_db_path: str | Path,
    output_dir: str | Path,
    config: BuildSnapshotConfig,
) -> BuildSnapshotResult:
    """Create a runtime SQLite snapshot, manifest, gzip artifact, and report."""

    build_path = Path(build_db_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = out_dir / "keyword-graph.sqlite3"
    manifest_path = out_dir / "snapshot-manifest.json"
    compressed_path = out_dir / "keyword-graph.sqlite3.gz"
    build_report_path = out_dir / "build-report.json"
    for path in (snapshot_path, manifest_path, compressed_path, build_report_path):
        if path.exists():
            path.unlink()

    build_conn = sqlite3.connect(build_path)
    build_conn.row_factory = sqlite3.Row
    try:
        report_payload = _build_report_payload(build_conn, config)
        build_report_bytes = _json_bytes(report_payload)
        build_report_path.write_bytes(build_report_bytes)
        build_report_sha256 = hashlib.sha256(build_report_bytes).hexdigest()

        snapshot_conn = sqlite3.connect(snapshot_path)
        snapshot_conn.row_factory = sqlite3.Row
        try:
            snapshot_conn.execute("pragma foreign_keys = on")
            migrate_runtime_snapshot(snapshot_conn)
            latest_observations = _latest_valid_observations(build_conn)
            _insert_meta(snapshot_conn, config, build_report_sha256)
            _insert_policy_meta(snapshot_conn, config)
            _project_surfaces(snapshot_conn, build_conn, config, latest_observations)
            _copy_table(
                snapshot_conn,
                build_conn,
                table="concepts",
                columns=(
                    "concept_id",
                    "canonical_label",
                    "concept_type",
                    "description",
                    "primary_surface_id",
                    "surface_count",
                    "jd_df",
                    "stability_score",
                    "review_status",
                    "created_at",
                    "updated_at",
                ),
                order_by="concept_id",
            )
            _copy_table(
                snapshot_conn,
                build_conn,
                table="concept_surfaces",
                columns=("concept_id", "surface_id", "confidence", "source", "status"),
                order_by="concept_id, surface_id",
            )
            _copy_table(
                snapshot_conn,
                build_conn,
                table="surface_relations",
                columns=(
                    "relation_id",
                    "from_surface_id",
                    "to_surface_id",
                    "relation_type",
                    "confidence",
                    "evidence_type",
                    "created_by",
                    "status",
                ),
                order_by="relation_id",
            )
            _copy_table(
                snapshot_conn,
                build_conn,
                table="cooccurrence_edges",
                columns=(
                    "edge_id",
                    "surface_id_a",
                    "surface_id_b",
                    "window_type",
                    "cooccur_count",
                    "pmi",
                    "jaccard",
                    "support",
                    "last_computed_at",
                ),
                order_by="edge_id",
            )
            _insert_latest_observations(snapshot_conn, latest_observations)
            snapshot_conn.commit()
        finally:
            snapshot_conn.close()

        compressed_path.write_bytes(gzip.compress(snapshot_path.read_bytes(), mtime=0))
        manifest_bytes = _manifest_bytes(
            config,
            snapshot_path=snapshot_path,
            compressed_path=compressed_path,
        )
        manifest_path.write_bytes(manifest_bytes)

        store = SQLiteSnapshotStore.open(snapshot_path, manifest_path)
        store.close()
    finally:
        build_conn.close()

    return BuildSnapshotResult(
        snapshot_path=snapshot_path,
        manifest_path=manifest_path,
        compressed_snapshot_path=compressed_path,
        build_report_path=build_report_path,
    )


def _build_report_payload(
    build_conn: sqlite3.Connection, config: BuildSnapshotConfig
) -> dict[str, Any]:
    counts = {}
    for table in (
        "surfaces",
        "concepts",
        "concept_surfaces",
        "surface_relations",
        "cooccurrence_edges",
        "cts_recall_observations",
    ):
        row = build_conn.execute(f"select count(*) from {table}").fetchone()
        counts[table] = row[0]
    return {
        "builder_run_id": config.builder_run_id,
        "built_at": config.built_at,
        "kg_snapshot_id": config.kg_snapshot_id,
        "source_corpus_version": config.source_corpus_version,
        "source_counts": counts,
    }


def _insert_meta(
    conn: sqlite3.Connection, config: BuildSnapshotConfig, build_report_sha256: str
) -> None:
    rows = {
        "kg_snapshot_id": config.kg_snapshot_id,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "built_at": config.built_at,
        "source_corpus_version": config.source_corpus_version,
        "builder_run_id": config.builder_run_id,
        "build_report_sha256": build_report_sha256,
        "manifest_sha256": "0" * 64,
        "cts_probe_window_start": config.cts_probe_window_start,
        "cts_probe_window_end": config.cts_probe_window_end,
        "created_by_package_version": __version__,
    }
    conn.executemany(
        "insert into snapshot_meta(key, value) values (?, ?)",
        sorted(rows.items()),
    )


def _insert_policy_meta(conn: sqlite3.Connection, config: BuildSnapshotConfig) -> None:
    rows = {
        "healthy_max_total": str(config.healthy_max_total),
        "healthy_min_total": str(config.healthy_min_total),
        "max_observation_age_days": str(config.max_observation_age_days),
        "selection_policy_version": SELECTION_POLICY_VERSION,
    }
    conn.executemany(
        "insert into selection_policy_meta(key, value) values (?, ?)",
        sorted(rows.items()),
    )


def _project_surfaces(
    snapshot_conn: sqlite3.Connection,
    build_conn: sqlite3.Connection,
    config: BuildSnapshotConfig,
    latest_observations: list[sqlite3.Row],
) -> None:
    totals_by_surface: dict[str, int] = {}
    latest_observed_by_surface: dict[str, str] = {}
    for row in latest_observations:
        surface_id = str(row["surface_id"])
        totals_by_surface[surface_id] = totals_by_surface.get(surface_id, 0) + int(
            row["total"]
        )
        current = latest_observed_by_surface.get(surface_id)
        if current is None or str(row["observed_at"]) > current:
            latest_observed_by_surface[surface_id] = str(row["observed_at"])

    rows = build_conn.execute(
        """
        select surface_id, text_raw, text_norm, display_text, language, token_class,
               query_safe, is_exact_phrase_preferred, ambiguity_score,
               specificity_score, jd_df, jd_tf_total, serving_status,
               created_at, updated_at
        from surfaces
        order by surface_id
        """
    ).fetchall()
    for row in rows:
        surface_id = str(row["surface_id"])
        recall_bucket = _recall_bucket(
            total=totals_by_surface.get(surface_id),
            observed_at=latest_observed_by_surface.get(surface_id),
            config=config,
        )
        snapshot_conn.execute(
            """
            insert into surfaces(
              surface_id, text_raw, text_norm, display_text, language, token_class,
              query_safe, is_exact_phrase_preferred, ambiguity_score, specificity_score,
              jd_df, jd_tf_total, recall_bucket, serving_status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["surface_id"],
                row["text_raw"],
                row["text_norm"],
                row["display_text"],
                row["language"],
                row["token_class"],
                row["query_safe"],
                row["is_exact_phrase_preferred"],
                row["ambiguity_score"],
                row["specificity_score"],
                row["jd_df"],
                row["jd_tf_total"],
                recall_bucket,
                row["serving_status"],
                row["created_at"],
                row["updated_at"],
            ),
        )


def _copy_table(
    snapshot_conn: sqlite3.Connection,
    build_conn: sqlite3.Connection,
    *,
    table: str,
    columns: tuple[str, ...],
    order_by: str,
) -> None:
    column_sql = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    rows = build_conn.execute(
        f"select {column_sql} from {table} order by {order_by}"
    ).fetchall()
    snapshot_conn.executemany(
        f"insert into {table}({column_sql}) values ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )


def _latest_valid_observations(build_conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = build_conn.execute(
        """
        select observation_id, surface_id, query_text, query_hash, query_mode, total,
               latency_ms, status, error_code, observed_at, cts_api_version,
               builder_run_id
        from cts_recall_observations
        where status = 'ok' and total is not null
        order by surface_id, query_hash, query_mode,
                 observed_at desc, observation_id desc
        """
    ).fetchall()
    latest: dict[tuple[str, str, str], sqlite3.Row] = {}
    for row in rows:
        key = (str(row["surface_id"]), str(row["query_hash"]), str(row["query_mode"]))
        latest.setdefault(key, row)
    return sorted(latest.values(), key=lambda row: str(row["observation_id"]))


def _insert_latest_observations(
    conn: sqlite3.Connection, observations: list[sqlite3.Row]
) -> None:
    for row in observations:
        conn.execute(
            """
            insert into cts_recall_observations(
              observation_id, surface_id, query_text, query_hash, query_mode,
              total, latency_ms, status, error_code, observed_at, cts_api_version,
              builder_run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["observation_id"],
                row["surface_id"],
                row["query_text"],
                row["query_hash"],
                row["query_mode"],
                row["total"],
                row["latency_ms"],
                row["status"],
                row["error_code"],
                row["observed_at"],
                row["cts_api_version"],
                row["builder_run_id"],
            ),
        )


def _recall_bucket(
    *, total: int | None, observed_at: str | None, config: BuildSnapshotConfig
) -> str:
    if total is None or observed_at is None:
        return "unknown"
    if _is_stale(observed_at, config):
        return "stale"
    if total == 0:
        return "zero"
    if total < config.healthy_min_total:
        return "too_narrow"
    if total > config.healthy_max_total:
        return "too_wide"
    return "healthy"


def _is_stale(observed_at: str, config: BuildSnapshotConfig) -> bool:
    observed = _parse_instant(observed_at)
    built = _parse_instant(config.built_at)
    return observed < built - timedelta(days=config.max_observation_age_days)


def _parse_instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _manifest_bytes(
    config: BuildSnapshotConfig, *, snapshot_path: Path, compressed_path: Path
) -> bytes:
    manifest = SnapshotManifest(
        kg_snapshot_id=config.kg_snapshot_id,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        selection_policy_version=SELECTION_POLICY_VERSION,
        built_at=config.built_at,
        source_corpus_version=config.source_corpus_version,
        builder_run_id=config.builder_run_id,
        artifacts={
            "sqlite": snapshot_path.name,
            "sqlite_gzip": compressed_path.name,
        },
        byte_sizes={
            "sqlite": snapshot_path.stat().st_size,
            "sqlite_gzip": compressed_path.stat().st_size,
        },
        sha256={
            "sqlite": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            "sqlite_gzip": hashlib.sha256(compressed_path.read_bytes()).hexdigest(),
        },
    )
    return _json_bytes(manifest.model_dump(mode="json"))


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
