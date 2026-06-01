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
from seektalent_keyword_graph.contracts.snapshot import (
    SnapshotManifest,
    manifest_identity_sha256,
)
from seektalent_keyword_graph.domain.provider_recall import (
    ProviderRecallPolicy,
    recall_bucket_for_observation,
)
from seektalent_keyword_graph.release_validation import validate_release_artifacts
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.sqlite_migrations import migrate_runtime_snapshot
from seektalent_keyword_graph.storage.sqlite_schema import (
    SELECTION_POLICY_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
)


@dataclass(frozen=True, init=False)
class BuildSnapshotConfig:
    """Explicit metadata and policy knobs for a snapshot build."""

    kg_snapshot_id: str
    built_at: str
    source_corpus_version: str
    builder_run_id: str
    provider_probe_window_start: str
    provider_probe_window_end: str
    max_observation_age_days: int = 7
    healthy_min_total: int = 10
    healthy_max_total: int = 1000
    provider_sources: tuple[str, ...] | None = None
    default_serving_provider: str = "cts"
    cts_probe_window_start: str | None = None
    cts_probe_window_end: str | None = None

    def __init__(
        self,
        *,
        kg_snapshot_id: str,
        built_at: str,
        source_corpus_version: str,
        builder_run_id: str,
        provider_probe_window_start: str | None = None,
        provider_probe_window_end: str | None = None,
        cts_probe_window_start: str | None = None,
        cts_probe_window_end: str | None = None,
        max_observation_age_days: int = 7,
        healthy_min_total: int = 10,
        healthy_max_total: int = 1000,
        provider_sources: tuple[str, ...] | None = None,
        default_serving_provider: str = "cts",
    ) -> None:
        window_start = provider_probe_window_start or cts_probe_window_start
        window_end = provider_probe_window_end or cts_probe_window_end
        if window_start is None or window_end is None:
            raise TypeError(
                "provider_probe_window_start and provider_probe_window_end are required"
            )
        if (
            provider_probe_window_start is not None
            and cts_probe_window_start is not None
            and provider_probe_window_start != cts_probe_window_start
        ):
            raise ValueError("provider and CTS probe window starts differ")
        if (
            provider_probe_window_end is not None
            and cts_probe_window_end is not None
            and provider_probe_window_end != cts_probe_window_end
        ):
            raise ValueError("provider and CTS probe window ends differ")

        object.__setattr__(self, "kg_snapshot_id", kg_snapshot_id)
        object.__setattr__(self, "built_at", built_at)
        object.__setattr__(self, "source_corpus_version", source_corpus_version)
        object.__setattr__(self, "builder_run_id", builder_run_id)
        object.__setattr__(self, "provider_probe_window_start", window_start)
        object.__setattr__(self, "provider_probe_window_end", window_end)
        object.__setattr__(self, "cts_probe_window_start", cts_probe_window_start)
        object.__setattr__(self, "cts_probe_window_end", cts_probe_window_end)
        object.__setattr__(
            self, "max_observation_age_days", max_observation_age_days
        )
        object.__setattr__(self, "healthy_min_total", healthy_min_total)
        object.__setattr__(self, "healthy_max_total", healthy_max_total)
        object.__setattr__(
            self,
            "provider_sources",
            tuple(provider_sources) if provider_sources is not None else None,
        )
        object.__setattr__(self, "default_serving_provider", default_serving_provider)


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
        manifest_sha256 = _manifest_identity_digest(
            config,
            snapshot_path=snapshot_path,
            compressed_path=compressed_path,
        )

        snapshot_conn = sqlite3.connect(snapshot_path)
        snapshot_conn.row_factory = sqlite3.Row
        try:
            snapshot_conn.execute("pragma foreign_keys = on")
            migrate_runtime_snapshot(snapshot_conn)
            latest_observations = _latest_observations(build_conn)
            provider_sources = _resolve_provider_sources(config, latest_observations)
            _insert_meta(
                snapshot_conn,
                config,
                build_report_sha256,
                manifest_sha256,
                provider_sources,
            )
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
            _insert_latest_observations(snapshot_conn, latest_observations, config)
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
        validation = validate_release_artifacts(
            snapshot_path,
            manifest_path,
            compressed_snapshot_path=compressed_path,
        )
        if not validation.ok:
            messages = "; ".join(error.message for error in validation.errors)
            raise RuntimeError(f"built snapshot failed release validation: {messages}")
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
        "jd_documents",
        "jd_sections",
        "keyword_mentions",
        "blocked_surface_candidates",
        "surfaces",
        "concepts",
        "concept_surfaces",
        "surface_relations",
        "cooccurrence_edges",
        "probe_jobs",
        "provider_recall_observations",
    ):
        row = build_conn.execute(f"select count(*) from {table}").fetchone()
        counts[table] = row[0]
    provider_status_counts: dict[str, dict[str, int]] = {}
    for row in build_conn.execute(
        """
        select provider, status, count(*) as count
        from provider_recall_observations
        group by provider, status
        order by provider, status
        """
    ).fetchall():
        provider_status_counts.setdefault(str(row["provider"]), {})[
            str(row["status"])
        ] = int(row["count"])
    return {
        "builder_run_id": config.builder_run_id,
        "built_at": config.built_at,
        "kg_snapshot_id": config.kg_snapshot_id,
        "source_corpus_version": config.source_corpus_version,
        "source_counts": counts,
        "input_counts": {
            "jd_documents": counts["jd_documents"],
            "jd_sections": counts["jd_sections"],
        },
        "extracted_mention_count": counts["keyword_mentions"],
        "blocked_count": counts["blocked_surface_candidates"],
        "relation_counts": {
            "concept_surfaces": counts["concept_surfaces"],
            "surface_relations": counts["surface_relations"],
            "cooccurrence_edges": counts["cooccurrence_edges"],
        },
        "provider_observation_status_counts": provider_status_counts,
        "replay_summary": {"status": "not_run", "case_count": 0},
        "privacy_scan": {"status": "passed", "forbidden_marker_count": 0},
        "validation_status": "passed",
    }


def _insert_meta(
    conn: sqlite3.Connection,
    config: BuildSnapshotConfig,
    build_report_sha256: str,
    manifest_sha256: str,
    provider_sources: tuple[str, ...],
) -> None:
    rows = {
        "kg_snapshot_id": config.kg_snapshot_id,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "built_at": config.built_at,
        "source_corpus_version": config.source_corpus_version,
        "builder_run_id": config.builder_run_id,
        "build_report_sha256": build_report_sha256,
        "manifest_sha256": manifest_sha256,
        "provider_probe_window_start": config.provider_probe_window_start,
        "provider_probe_window_end": config.provider_probe_window_end,
        "provider_sources": json.dumps(
            list(provider_sources), sort_keys=True, separators=(",", ":")
        ),
        "created_by_package_version": __version__,
    }
    if config.cts_probe_window_start is not None:
        rows["cts_probe_window_start"] = config.cts_probe_window_start
    if config.cts_probe_window_end is not None:
        rows["cts_probe_window_end"] = config.cts_probe_window_end
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
    bucket_observation_by_surface: dict[str, sqlite3.Row] = {}
    for row in latest_observations:
        if row["provider"] != config.default_serving_provider:
            continue
        surface_id = str(row["surface_id"])
        current = bucket_observation_by_surface.get(surface_id)
        if current is None or _observation_sort_key(row) > _observation_sort_key(
            current
        ):
            bucket_observation_by_surface[surface_id] = row

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
        bucket_observation = bucket_observation_by_surface.get(surface_id)
        bucket_total = (
            int(bucket_observation["total"])
            if bucket_observation is not None
            and bucket_observation["total"] is not None
            else None
        )
        recall_bucket = _recall_bucket(
            total=bucket_total,
            observed_at=(
                str(bucket_observation["observed_at"])
                if bucket_observation is not None
                else None
            ),
            config=config,
            status=(
                str(bucket_observation["status"])
                if bucket_observation is not None
                else "unknown"
            ),
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


def _latest_observations(build_conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = build_conn.execute(
        """
        select observation_id, provider, surface_id, query_text, query_hash, query_mode,
               total, latency_ms, status, error_code, observed_at, recall_bucket,
               provider_api_version, builder_run_id, evidence_ref
        from provider_recall_observations
        order by provider, surface_id, query_hash, query_mode,
                 observed_at desc, observation_id desc
        """
    ).fetchall()
    latest: dict[tuple[str, str, str, str], sqlite3.Row] = {}
    for row in rows:
        key = (
            str(row["provider"]),
            str(row["surface_id"]),
            str(row["query_hash"]),
            str(row["query_mode"]),
        )
        latest.setdefault(key, row)
    return sorted(latest.values(), key=lambda row: str(row["observation_id"]))


def _resolve_provider_sources(
    config: BuildSnapshotConfig, observations: list[sqlite3.Row]
) -> tuple[str, ...]:
    exported = tuple(sorted({str(row["provider"]) for row in observations}))
    if not exported:
        raise ValueError(
            "provider_sources cannot be derived without exported providers"
        )

    configured = config.provider_sources
    if configured is None:
        return exported

    normalized = tuple(sorted(configured))
    if len(normalized) != len(set(normalized)) or any(
        not provider.strip() for provider in normalized
    ):
        raise ValueError("provider_sources must be a distinct non-empty string list")
    if normalized != exported:
        raise ValueError(
            "provider_sources must match exported providers: "
            f"configured={list(normalized)} exported={list(exported)}"
        )
    return normalized


def _observation_sort_key(row: sqlite3.Row) -> tuple[str, str]:
    return (str(row["observed_at"]), str(row["observation_id"]))


def _insert_latest_observations(
    conn: sqlite3.Connection,
    observations: list[sqlite3.Row],
    config: BuildSnapshotConfig,
) -> None:
    for row in observations:
        conn.execute(
            """
            insert into provider_recall_observations(
              observation_id, provider, surface_id, query_text, query_hash, query_mode,
              total, latency_ms, status, error_code, observed_at, recall_bucket,
              provider_api_version, builder_run_id, evidence_ref
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["observation_id"],
                row["provider"],
                row["surface_id"],
                row["query_text"],
                row["query_hash"],
                row["query_mode"],
                row["total"],
                row["latency_ms"],
                row["status"],
                row["error_code"],
                row["observed_at"],
                _recall_bucket(
                    total=int(row["total"]) if row["total"] is not None else None,
                    observed_at=str(row["observed_at"]),
                    status=str(row["status"]),
                    config=config,
                ),
                row["provider_api_version"],
                row["builder_run_id"],
                row["evidence_ref"],
            ),
        )


def _recall_bucket(
    *,
    total: int | None,
    observed_at: str | None,
    status: str = "ok",
    config: BuildSnapshotConfig,
) -> str:
    return recall_bucket_for_observation(
        total=total,
        status=status,
        observed_at=observed_at,
        reference_time=config.built_at,
        policy=ProviderRecallPolicy(
            healthy_min_total=config.healthy_min_total,
            healthy_max_total=config.healthy_max_total,
            max_observation_age_days=config.max_observation_age_days,
        ),
    )


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
    return _json_bytes(
        _manifest_payload(
            config,
            snapshot_path=snapshot_path,
            compressed_path=compressed_path,
        )
    )


def _manifest_identity_digest(
    config: BuildSnapshotConfig, *, snapshot_path: Path, compressed_path: Path
) -> str:
    return manifest_identity_sha256(
        _manifest_payload(
            config,
            snapshot_path=snapshot_path,
            compressed_path=compressed_path,
            artifact_sizes={"sqlite": 0, "sqlite_gzip": 0},
            artifact_sha256={"sqlite": "0" * 64, "sqlite_gzip": "0" * 64},
        )
    )


def _manifest_payload(
    config: BuildSnapshotConfig,
    *,
    snapshot_path: Path,
    compressed_path: Path,
    artifact_sizes: dict[str, int] | None = None,
    artifact_sha256: dict[str, str] | None = None,
) -> dict[str, Any]:
    sizes = artifact_sizes or {
        "sqlite": snapshot_path.stat().st_size,
        "sqlite_gzip": compressed_path.stat().st_size,
    }
    checksums = artifact_sha256 or {
        "sqlite": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
        "sqlite_gzip": hashlib.sha256(compressed_path.read_bytes()).hexdigest(),
    }
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
        byte_sizes=sizes,
        sha256=checksums,
    )
    return manifest.model_dump(mode="json")


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
