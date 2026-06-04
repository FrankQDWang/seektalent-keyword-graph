"""SQLite migration runners and schema inspection helpers."""

from __future__ import annotations

import sqlite3

from seektalent_keyword_graph.storage.sqlite_schema import (
    BUILD_SCHEMA_SQL,
    BUILD_SCHEMA_VERSION,
    RUNTIME_SNAPSHOT_SCHEMA_SQL,
)


def migrate_build_db(conn: sqlite3.Connection) -> None:
    """Apply the current build database schema migration."""
    conn.executescript(BUILD_SCHEMA_SQL)
    conn.execute(
        "insert or ignore into schema_migrations(version) values (?)",
        (BUILD_SCHEMA_VERSION,),
    )
    conn.commit()


def migrate_runtime_snapshot(conn: sqlite3.Connection) -> None:
    """Apply the current runtime snapshot schema to a writable SQLite DB."""
    conn.executescript(RUNTIME_SNAPSHOT_SCHEMA_SQL)
    conn.commit()


def sqlite_object_names(conn: sqlite3.Connection, object_type: str) -> set[str]:
    """Return non-internal SQLite object names of a given type."""
    return {
        row[0]
        for row in conn.execute(
            "select name from sqlite_master "
            "where type = ? and name not like 'sqlite_%'",
            (object_type,),
        )
    }
