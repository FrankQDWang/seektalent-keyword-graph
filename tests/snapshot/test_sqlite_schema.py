from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.runtime.errors import SnapshotSchemaError
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.privacy_scan import (
    ForbiddenPrivacyMarker,
    scan_forbidden_markers,
)
from seektalent_keyword_graph.storage.sqlite_migrations import (
    migrate_build_db,
    migrate_runtime_snapshot,
)
from seektalent_keyword_graph.storage.sqlite_schema import (
    BUILD_INDEXES,
    BUILD_TABLES,
    REQUIRED_SNAPSHOT_META_KEYS,
    SNAPSHOT_INDEXES,
    SNAPSHOT_TABLES,
)


def object_names(conn: sqlite3.Connection, object_type: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master "
            "where type = ? and name not like 'sqlite_%'",
            (object_type,),
        )
    }


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


def test_build_db_migration_creates_spec_tables_and_indexes(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "build.sqlite3")
    try:
        migrate_build_db(conn)

        assert object_names(conn, "table") >= BUILD_TABLES
        assert object_names(conn, "index") >= BUILD_INDEXES
        assert conn.execute("select version from schema_migrations").fetchall() == [
            ("build-v1",)
        ]
    finally:
        conn.close()


def test_build_db_migration_is_idempotent(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "build.sqlite3")
    try:
        migrate_build_db(conn)
        first_tables = object_names(conn, "table")
        first_indexes = object_names(conn, "index")

        migrate_build_db(conn)

        assert object_names(conn, "table") == first_tables
        assert object_names(conn, "index") == first_indexes
        assert conn.execute("select count(*) from schema_migrations").fetchone() == (1,)
    finally:
        conn.close()


def test_runtime_snapshot_schema_creates_required_tables_and_indexes(
    tmp_path: Path,
) -> None:
    conn = sqlite3.connect(tmp_path / "snapshot.sqlite3")
    try:
        migrate_runtime_snapshot(conn)

        assert object_names(conn, "table") >= SNAPSHOT_TABLES
        assert object_names(conn, "index") >= SNAPSHOT_INDEXES
    finally:
        conn.close()


@pytest.mark.parametrize(
    "marker",
    [
        "KEYWORD_GRAPH_CTS_API_KEY",
        "tenant_secret",
        "candidate_list",
        "candidate_id",
        "resume_text",
        ".env",
    ],
)
def test_privacy_scanner_catches_forbidden_markers(
    tmp_path: Path, marker: str
) -> None:
    path = tmp_path / "artifact.sqlite3"
    path.write_bytes(f"public bytes then {marker}".encode())

    findings = scan_forbidden_markers(path)

    assert findings == [ForbiddenPrivacyMarker(marker=marker)]


def test_valid_runtime_snapshot_opens_read_only(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)

    store = SQLiteSnapshotStore.open(path)
    try:
        assert store.meta()["snapshot_schema_version"] == "snapshot-v1"
        with pytest.raises(sqlite3.OperationalError):
            store.connection.execute(
                "insert into snapshot_meta(key, value) values('x','y')"
            )
    finally:
        store.close()


def test_runtime_snapshot_missing_required_index_fails(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.sqlite3"
    make_snapshot(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute("drop index idx_snapshot_surfaces_text_norm")
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(SnapshotSchemaError, match="idx_snapshot_surfaces_text_norm"):
        SQLiteSnapshotStore.open(path)
