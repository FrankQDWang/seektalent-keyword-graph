from __future__ import annotations

import sqlite3
from pathlib import Path


def build(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
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
        insert into snapshot_meta values ('kg_fixture', 'snapshot-v1', 'policy-v1');
        insert into concepts values ('concept_k8s', 'Kubernetes');
        insert into surfaces values ('surface_k8s', 'k8s', 'k8s', 1, 58692, 'success');
        insert into concept_surfaces values ('concept_k8s', 'surface_k8s');
        insert into selection_policy_meta values ('policy-v1');
        """
    )
    conn.close()


if __name__ == "__main__":
    build(Path("tests/fixtures/snapshots/minimal.sqlite3"))
