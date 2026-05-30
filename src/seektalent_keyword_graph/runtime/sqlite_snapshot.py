from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.runtime.errors import (
    SnapshotIntegrityError,
    SnapshotUnavailableError,
    UnsupportedSnapshotError,
)

SUPPORTED_SNAPSHOT_SCHEMA_VERSION = "snapshot-v1"
REQUIRED_TABLES = {
    "snapshot_meta",
    "concepts",
    "surfaces",
    "concept_surfaces",
    "surface_relations",
    "cooccurrence_edges",
    "cts_recall_observations",
    "selection_policy_meta",
}


class SQLiteSnapshot:
    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: str | Path) -> SQLiteSnapshot:
        snapshot_path = Path(path)
        if not snapshot_path.exists():
            raise SnapshotUnavailableError(f"Snapshot not found: {snapshot_path}")
        uri = f"file:{snapshot_path}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise SnapshotUnavailableError(f"Snapshot cannot be opened: {snapshot_path}") from exc
        snapshot = cls(snapshot_path, connection)
        snapshot.validate()
        return snapshot

    def validate(self) -> None:
        try:
            table_rows = self.connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        except sqlite3.Error as exc:
            raise SnapshotIntegrityError("Snapshot catalog cannot be read") from exc

        existing_tables = {row["name"] for row in table_rows}
        missing_tables = REQUIRED_TABLES - existing_tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise SnapshotIntegrityError(f"Snapshot missing required tables: {missing}")

        meta = self.meta()
        if not meta:
            raise SnapshotIntegrityError("Snapshot metadata is empty")
        if meta["snapshot_schema_version"] != SUPPORTED_SNAPSHOT_SCHEMA_VERSION:
            raise UnsupportedSnapshotError(
                f"Unsupported snapshot schema: {meta['snapshot_schema_version']}"
            )

    def meta(self) -> dict[str, Any]:
        try:
            row = self.connection.execute(
                "select kg_snapshot_id, snapshot_schema_version, selection_policy_version "
                "from snapshot_meta limit 1"
            ).fetchone()
        except sqlite3.Error as exc:
            raise SnapshotIntegrityError("Snapshot metadata cannot be read") from exc
        if row is None:
            return {}
        return dict(row)
