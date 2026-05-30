import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.runtime.errors import (
    SnapshotIntegrityError,
    SnapshotUnavailableError,
    UnsupportedSnapshotError,
)
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot

FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")
REQUIRED_RUNTIME_TABLE_SQL = """
create table concepts (
  concept_id text primary key,
  canonical_surface text not null
);
create table surfaces (
  surface_id text primary key,
  display_text text not null,
  normalized_text text not null,
  query_safe integer not null,
  latest_cts_total integer,
  latest_cts_status text not null
);
create table concept_surfaces (
  concept_id text not null,
  surface_id text not null
);
create table surface_relations (
  source_surface_id text not null,
  target_surface_id text not null,
  relation_type text not null,
  evidence_score real not null
);
create table cooccurrence_edges (
  source_concept_id text not null,
  target_concept_id text not null,
  weight real not null
);
create table cts_recall_observations (
  surface_id text not null,
  total integer,
  status text not null,
  observed_at text not null
);
create table selection_policy_meta (
  selection_policy_version text not null
);
"""


def write_snapshot(path: Path, script: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.close()


def test_snapshot_meta_loads():
    snapshot = SQLiteSnapshot.open(FIXTURE)
    meta = snapshot.meta()

    assert meta["kg_snapshot_id"] == "kg_fixture"
    assert meta["snapshot_schema_version"] == "snapshot-v1"


def test_missing_snapshot_raises():
    with pytest.raises(SnapshotUnavailableError):
        SQLiteSnapshot.open("missing.sqlite3")


def test_unsupported_snapshot_schema_raises(tmp_path):
    path = tmp_path / "unsupported.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_bad', 'snapshot-v999', 'policy-v1');
        """
        + REQUIRED_RUNTIME_TABLE_SQL,
    )

    with pytest.raises(UnsupportedSnapshotError):
        SQLiteSnapshot.open(path)


def test_missing_required_table_raises(tmp_path):
    path = tmp_path / "missing_table.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_bad', 'snapshot-v1', 'policy-v1');
        """,
    )

    with pytest.raises(SnapshotIntegrityError):
        SQLiteSnapshot.open(path)


def test_empty_snapshot_meta_raises(tmp_path):
    path = tmp_path / "empty_meta.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        """
        + REQUIRED_RUNTIME_TABLE_SQL,
    )

    with pytest.raises(SnapshotIntegrityError):
        SQLiteSnapshot.open(path)
