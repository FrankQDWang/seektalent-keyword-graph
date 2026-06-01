"""Read-only SQLite runtime snapshot adapter."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from seektalent_keyword_graph.contracts.snapshot import manifest_identity_sha256
from seektalent_keyword_graph.runtime.errors import (
    SnapshotChecksumError,
    SnapshotFormatError,
    SnapshotPrivacyError,
    SnapshotSchemaError,
    UnsupportedSnapshotVersionError,
)
from seektalent_keyword_graph.storage.privacy_scan import scan_forbidden_markers
from seektalent_keyword_graph.storage.sqlite_migrations import sqlite_object_names
from seektalent_keyword_graph.storage.sqlite_schema import (
    REQUIRED_SNAPSHOT_META_KEYS,
    SELECTION_POLICY_VERSION,
    SNAPSHOT_INDEXES,
    SNAPSHOT_SCHEMA_VERSION,
    SNAPSHOT_TABLES,
)


class SQLiteSnapshotStore:
    """Validated read-only access to a runtime SQLite snapshot."""

    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self.connection = connection
        self.path = path
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(
        cls, snapshot_path: str | Path, manifest_path: str | Path | None = None
    ) -> SQLiteSnapshotStore:
        path = Path(snapshot_path)
        if not path.is_file():
            raise SnapshotFormatError(f"snapshot file does not exist: {path}")

        findings = scan_forbidden_markers(path)
        if findings:
            markers = ", ".join(finding.marker for finding in findings)
            raise SnapshotPrivacyError(f"snapshot contains forbidden marker(s): {markers}")

        if manifest_path is not None:
            _validate_manifest_checksum(path, Path(manifest_path))

        uri = f"file:{quote(str(path.resolve()))}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
            conn.execute("pragma foreign_keys = on")
            store = cls(conn, path)
            store.validate()
            if manifest_path is not None:
                store._validate_manifest_identity(Path(manifest_path))
        except SnapshotPrivacyError:
            raise
        except SnapshotChecksumError:
            raise
        except UnsupportedSnapshotVersionError:
            raise
        except SnapshotSchemaError:
            raise
        except sqlite3.DatabaseError as exc:
            raise SnapshotFormatError(f"invalid SQLite snapshot: {path}") from exc

        return store

    def close(self) -> None:
        self.connection.close()

    def validate(self) -> None:
        try:
            self.connection.execute("pragma schema_version").fetchone()
            self._validate_tables()
            self._validate_indexes()
            meta = self.meta()
            self._validate_meta(meta)
            self._validate_references()
            self._validate_privacy_in_text_columns()
        except sqlite3.DatabaseError as exc:
            raise SnapshotFormatError(f"invalid SQLite snapshot: {self.path}") from exc

    def meta(self) -> dict[str, str]:
        try:
            rows = self.connection.execute("select key, value from snapshot_meta").fetchall()
        except sqlite3.DatabaseError as exc:
            raise SnapshotSchemaError("missing required table snapshot_meta") from exc
        return {row["key"]: row["value"] for row in rows}

    def get_surface_by_norm(self, text_norm: str) -> dict[str, object] | None:
        return self._fetch_one(
            "select * from surfaces where text_norm = ? and serving_status = 'active'",
            (text_norm,),
        )

    def get_surface(self, surface_id: str) -> dict[str, object] | None:
        return self._fetch_one("select * from surfaces where surface_id = ?", (surface_id,))

    def get_concept(self, concept_id: str) -> dict[str, object] | None:
        return self._fetch_one("select * from concepts where concept_id = ?", (concept_id,))

    def list_concept_surfaces(self, concept_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from concept_surfaces where concept_id = ? order by confidence desc, surface_id",
            (concept_id,),
        )

    def list_surface_concepts(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from concept_surfaces where surface_id = ? order by confidence desc, concept_id",
            (surface_id,),
        )

    def list_related_surfaces(
        self, surface_id: str, relation_type: str | None = None
    ) -> list[dict[str, object]]:
        if relation_type is None:
            return self._fetch_all(
                "select * from surface_relations where from_surface_id = ? and status = 'active' "
                "order by confidence desc, to_surface_id",
                (surface_id,),
            )
        return self._fetch_all(
            "select * from surface_relations where from_surface_id = ? and relation_type = ? "
            "and status = 'active' order by confidence desc, to_surface_id",
            (surface_id, relation_type),
        )

    def list_cooccurrence_edges(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from cooccurrence_edges where surface_id_a = ? or surface_id_b = ? "
            "order by support desc, edge_id",
            (surface_id, surface_id),
        )

    def list_recall_observations(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from cts_recall_observations where surface_id = ? "
            "order by observed_at desc, observation_id",
            (surface_id,),
        )

    def _validate_tables(self) -> None:
        missing = sorted(SNAPSHOT_TABLES - sqlite_object_names(self.connection, "table"))
        if missing:
            raise SnapshotSchemaError(
                f"snapshot missing required table(s): {', '.join(missing)}"
            )

    def _validate_indexes(self) -> None:
        missing = sorted(SNAPSHOT_INDEXES - sqlite_object_names(self.connection, "index"))
        if missing:
            raise SnapshotSchemaError(
                f"snapshot missing required index(es): {', '.join(missing)}"
            )

    def _validate_meta(self, meta: dict[str, str]) -> None:
        missing = sorted(REQUIRED_SNAPSHOT_META_KEYS - set(meta))
        if missing:
            raise SnapshotSchemaError(
                f"snapshot missing required meta key(s): {', '.join(missing)}"
            )
        schema_version = meta["snapshot_schema_version"]
        if schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise UnsupportedSnapshotVersionError(
                f"unsupported snapshot schema version: {schema_version}"
            )
        policy_version = meta["selection_policy_version"]
        if policy_version != SELECTION_POLICY_VERSION:
            raise SnapshotSchemaError(
                f"unsupported selection policy version: {policy_version}"
            )

    def _validate_references(self) -> None:
        orphan_checks = (
            (
                "concepts.primary_surface_id",
                """
                select c.concept_id
                from concepts c
                left join surfaces s on s.surface_id = c.primary_surface_id
                where c.primary_surface_id is not null and s.surface_id is null
                limit 1
                """,
            ),
            (
                "concept_surfaces.concept_id",
                """
                select cs.concept_id
                from concept_surfaces cs
                left join concepts c on c.concept_id = cs.concept_id
                where c.concept_id is null
                limit 1
                """,
            ),
            (
                "concept_surfaces.surface_id",
                """
                select cs.surface_id
                from concept_surfaces cs
                left join surfaces s on s.surface_id = cs.surface_id
                where s.surface_id is null
                limit 1
                """,
            ),
        )
        for label, sql in orphan_checks:
            row = self.connection.execute(sql).fetchone()
            if row is not None:
                raise SnapshotSchemaError(
                    f"snapshot has orphan reference in {label}: {row[0]}"
                )

        foreign_key_failure = self.connection.execute(
            "pragma foreign_key_check"
        ).fetchone()
        if foreign_key_failure is not None:
            table = foreign_key_failure[0]
            rowid = foreign_key_failure[1]
            parent = foreign_key_failure[2]
            raise SnapshotSchemaError(
                f"snapshot foreign key check failed: {table} row {rowid} references {parent}"
            )

    def _validate_privacy_in_text_columns(self) -> None:
        rows = self.connection.execute(
            """
            select text_raw as value from surfaces
            union all select text_norm from surfaces
            union all select display_text from surfaces
            union all select canonical_label from concepts
            union all select description from concepts
            union all select query_text from cts_recall_observations
            """
        ).fetchall()
        haystack = "\n".join(str(row["value"]) for row in rows).lower()
        markers = [
            marker
            for marker in (
                "keyword_graph_cts_",
                "tenant_secret",
                "candidate_list",
                "candidate_id",
                "resume_text",
                ".env",
            )
            if marker in haystack
        ]
        if markers:
            raise SnapshotPrivacyError(
                f"snapshot contains forbidden marker(s): {', '.join(markers)}"
            )

    def _fetch_one(
        self, sql: str, parameters: tuple[object, ...]
    ) -> dict[str, object] | None:
        row = self.connection.execute(sql, parameters).fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetch_all(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute(sql, parameters).fetchall()]

    def _validate_manifest_identity(self, manifest_path: Path) -> None:
        manifest = _read_manifest_payload(manifest_path)
        expected = self.meta()["manifest_sha256"]
        actual = manifest_identity_sha256(manifest)
        if actual != expected:
            raise SnapshotChecksumError(
                f"manifest identity sha256 mismatch: expected {expected}, got {actual}"
            )


def _validate_manifest_checksum(snapshot_path: Path, manifest_path: Path) -> None:
    if not manifest_path.is_file():
        raise SnapshotChecksumError(f"manifest file does not exist: {manifest_path}")
    manifest = _read_manifest_payload(manifest_path)

    digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    expected = _snapshot_checksum_from_manifest(manifest, snapshot_path)
    if expected != digest:
        raise SnapshotChecksumError(
            f"snapshot sha256 mismatch: expected {expected}, got {digest}"
        )

    expected_size = _snapshot_size_from_manifest(manifest, snapshot_path)
    actual_size = snapshot_path.stat().st_size
    if expected_size != actual_size:
        raise SnapshotChecksumError(
            f"snapshot byte size mismatch: expected {expected_size}, got {actual_size}"
        )


def _read_manifest_payload(manifest_path: Path) -> dict[str, object]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotChecksumError(f"manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(manifest, dict):
        raise SnapshotChecksumError("manifest must be a JSON object")
    return manifest


def _snapshot_checksum_from_manifest(
    manifest: dict[str, object], snapshot_path: Path
) -> str:
    sha_map = manifest.get("sha256")
    artifacts = manifest.get("artifacts")
    if isinstance(sha_map, dict) and isinstance(artifacts, dict):
        for key, artifact_path in artifacts.items():
            if Path(str(artifact_path)).name == snapshot_path.name:
                checksum = sha_map.get(key)
                if isinstance(checksum, str):
                    return checksum
    raise SnapshotChecksumError("manifest missing snapshot sha256")


def _snapshot_size_from_manifest(manifest: dict[str, object], snapshot_path: Path) -> int:
    size_map = manifest.get("byte_sizes")
    artifacts = manifest.get("artifacts")
    if isinstance(size_map, dict) and isinstance(artifacts, dict):
        for key, artifact_path in artifacts.items():
            if Path(str(artifact_path)).name == snapshot_path.name:
                size = size_map.get(key)
                if isinstance(size, int):
                    return size
    raise SnapshotChecksumError("manifest missing snapshot byte size")
