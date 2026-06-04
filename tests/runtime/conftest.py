from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.domain.classification import classify_surface
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore
from seektalent_keyword_graph.storage.sqlite_migrations import migrate_runtime_snapshot
from seektalent_keyword_graph.storage.sqlite_schema import REQUIRED_SNAPSHOT_META_KEYS


def _make_snapshot(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        migrate_runtime_snapshot(conn)
        conn.executemany(
            "insert into snapshot_meta(key, value) values (?, ?)",
            [(key, f"{key}-value") for key in REQUIRED_SNAPSHOT_META_KEYS],
        )
        conn.execute(
            "update snapshot_meta set value = ? where key = ?",
            ("kg-test-snapshot", "kg_snapshot_id"),
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
            ("provider_sources", '["boss", "cts", "liepin"]'),
        )
        for surface_id, text, bucket in [
            ("surface:python", "Python", "healthy"),
            ("surface:kubernetes", "Kubernetes", "too_wide"),
            ("surface:docker", "Docker", "healthy"),
            ("surface:react", "React", "zero"),
            ("surface:react-js", "React.js", "healthy"),
            ("surface:terraform", "Terraform", "zero"),
            ("surface:kafka", "Kafka", "stale"),
            ("surface:apache-kafka", "Apache Kafka", "healthy"),
            ("surface:rails", "Rails", "zero"),
            ("surface:ruby-on-rails", "Ruby on Rails", "healthy"),
            ("surface:js", "JS", "zero"),
            ("surface:javascript", "JavaScript", "healthy"),
            ("surface:nodejs", "NodeJS", "zero"),
            ("surface:node.js", "Node.js", "healthy"),
            ("surface:vue", "Vue", "zero"),
            ("surface:vue-3", "Vue 3", "healthy"),
            ("surface:aiops", "AIOps", "zero"),
            ("surface:llmops", "LLMOps", "unknown"),
            ("surface:vector-search", "Vector Search", "healthy"),
            ("surface:aaa-low-quality", "Aaa Low Quality", "healthy"),
            ("surface:zzz-high-quality", "Zzz High Quality", "healthy"),
        ]:
            classification = classify_surface(text)
            quality_overrides = {
                "surface:aaa-low-quality": (0.88, 0.12),
                "surface:zzz-high-quality": (0.08, 0.94),
            }
            ambiguity_score, specificity_score = quality_overrides.get(
                surface_id,
                (classification.ambiguity_score, classification.specificity_score),
            )
            conn.execute(
                """
                insert into surfaces(
                  surface_id, text_raw, text_norm, display_text, language, token_class,
                  query_safe, is_exact_phrase_preferred, ambiguity_score,
                  specificity_score, jd_df, jd_tf_total, recall_bucket,
                  serving_status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    surface_id,
                    text,
                    classification.text_norm,
                    text,
                    classification.language,
                    classification.token_class,
                    int(classification.query_safe),
                    int(classification.is_exact_phrase_preferred),
                    ambiguity_score,
                    specificity_score,
                    10,
                    20,
                    bucket,
                    "2026-05-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                ),
            )
        concepts = [
            ("concept:python", "Python", "language", "surface:python", 0.98),
            (
                "concept:kubernetes",
                "Kubernetes",
                "platform",
                "surface:kubernetes",
                0.97,
            ),
            ("concept:docker", "Docker", "tool", "surface:docker", 0.94),
            ("concept:react", "React", "framework", "surface:react", 0.93),
            ("concept:terraform", "Terraform", "tool", "surface:terraform", 0.91),
            ("concept:kafka", "Kafka", "tool", "surface:kafka", 0.94),
            (
                "concept:rails",
                "Ruby on Rails",
                "framework",
                "surface:ruby-on-rails",
                0.92,
            ),
            (
                "concept:javascript",
                "JavaScript",
                "language",
                "surface:javascript",
                0.94,
            ),
            ("concept:node.js", "Node.js", "framework", "surface:node.js", 0.91),
            ("concept:vue", "Vue", "framework", "surface:vue", 0.9),
            ("concept:llmops", "LLMOps", "method", "surface:llmops", 0.76),
            (
                "concept:vector-search",
                "Vector Search",
                "method",
                "surface:vector-search",
                0.9,
            ),
            (
                "concept:low-quality",
                "Aaa Low Quality",
                "skill",
                "surface:aaa-low-quality",
                0.62,
            ),
            (
                "concept:high-quality",
                "Zzz High Quality",
                "skill",
                "surface:zzz-high-quality",
                0.97,
            ),
        ]
        for concept_id, label, concept_type, primary_surface_id, confidence in concepts:
            conn.execute(
                """
                insert into concepts(
                  concept_id, canonical_label, concept_type, description,
                  primary_surface_id, surface_count, jd_df, stability_score,
                  review_status, created_at, updated_at
                ) values (?, ?, ?, ?, ?, 1, 10, ?, 'approved', ?, ?)
                """,
                (
                    concept_id,
                    label,
                    concept_type,
                    f"{label} concept",
                    primary_surface_id,
                    confidence,
                    "2026-05-01T00:00:00Z",
                    "2026-05-01T00:00:00Z",
                ),
            )
            conn.execute(
                """
                insert into concept_surfaces(
                  concept_id, surface_id, confidence, source, status
                )
                values (?, ?, ?, 'fixture', 'active')
                """,
                (concept_id, primary_surface_id, confidence),
            )
        conn.execute(
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            )
            values ('concept:react', 'surface:react-js', 0.89, 'fixture', 'active')
            """
        )
        conn.execute(
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            )
            values ('concept:rails', 'surface:rails', 0.88, 'fixture', 'active')
            """
        )
        conn.execute(
            """
            insert into concept_surfaces(
              concept_id, surface_id, confidence, source, status
            )
            values ('concept:kafka', 'surface:apache-kafka', 0.9, 'fixture', 'active')
            """
        )
        for concept_id, surface_id, confidence in [
            ("concept:javascript", "surface:js", 0.88),
            ("concept:node.js", "surface:nodejs", 0.87),
            ("concept:vue", "surface:vue-3", 0.86),
            ("concept:llmops", "surface:aiops", 0.84),
        ]:
            conn.execute(
                """
                insert into concept_surfaces(
                  concept_id, surface_id, confidence, source, status
                )
                values (?, ?, ?, 'fixture', 'active')
                """,
                (concept_id, surface_id, confidence),
            )
        for relation_id, from_id, to_id, relation_type in [
            ("relation:react-alias", "surface:react", "surface:react-js", "alias"),
            ("relation:kafka-alias", "surface:kafka", "surface:apache-kafka", "alias"),
            (
                "relation:rails-reverse-alias",
                "surface:ruby-on-rails",
                "surface:rails",
                "alias",
            ),
            (
                "relation:rails-equivalent",
                "surface:rails",
                "surface:ruby-on-rails",
                "equivalent",
            ),
            (
                "relation:js-abbreviation",
                "surface:js",
                "surface:javascript",
                "abbreviation",
            ),
            (
                "relation:node-normalized",
                "surface:nodejs",
                "surface:node.js",
                "normalized_form",
            ),
            (
                "relation:vue-version",
                "surface:vue-3",
                "surface:vue",
                "version_variant",
            ),
            (
                "relation:aiops-alias",
                "surface:aiops",
                "surface:llmops",
                "alias",
            ),
        ]:
            conn.execute(
                """
                insert into surface_relations(
                  relation_id, from_surface_id, to_surface_id, relation_type,
                  confidence, evidence_type, created_by, status
                ) values (?, ?, ?, ?, 0.95, 'fixture', 'fixture', 'active')
                """,
                (relation_id, from_id, to_id, relation_type),
            )
        conn.execute(
            """
            insert into cooccurrence_edges(
              edge_id, surface_id_a, surface_id_b, window_type, cooccur_count,
              pmi, jaccard, support, last_computed_at
            ) values (
              'edge:kubernetes-docker', 'surface:kubernetes', 'surface:docker',
              'jd', 8, 3.1, 0.4, 0.88, '2026-05-01T00:00:00Z'
            )
            """
        )
        cts_observations = [
            ("surface:python", 42, "ok", "2026-05-01T00:00:00Z"),
            ("surface:kubernetes", 900, "ok", "2026-05-01T00:00:00Z"),
            ("surface:docker", 60, "ok", "2026-05-01T00:00:00Z"),
            ("surface:react", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:react-js", 50, "ok", "2026-05-01T00:00:00Z"),
            ("surface:terraform", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:kafka", 80, "ok", "2025-01-01T00:00:00Z"),
            ("surface:apache-kafka", 55, "ok", "2026-05-01T00:00:00Z"),
            ("surface:rails", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:ruby-on-rails", 48, "ok", "2026-05-01T00:00:00Z"),
            ("surface:js", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:javascript", 44, "ok", "2026-05-01T00:00:00Z"),
            ("surface:nodejs", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:node.js", 30, "ok", "2026-05-01T00:00:00Z"),
            ("surface:vue", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:vue-3", 52, "ok", "2026-05-01T00:00:00Z"),
            ("surface:aiops", 0, "ok", "2026-05-01T00:00:00Z"),
            ("surface:llmops", None, "unknown", "2026-05-01T00:00:00Z"),
            ("surface:vector-search", 35, "ok", "2026-05-01T00:00:00Z"),
            ("surface:aaa-low-quality", 28, "ok", "2026-05-01T00:00:00Z"),
            ("surface:zzz-high-quality", 29, "ok", "2026-05-01T00:00:00Z"),
        ]
        liepin_overrides = {
            "surface:python": (7, "ok", "too_narrow"),
            "surface:kubernetes": (40, "ok", "healthy"),
            "surface:react": (12, "ok", "healthy"),
            "surface:aiops": (0, "ok", "zero"),
            "surface:llmops": (36, "ok", "healthy"),
        }
        boss_overrides = {
            "surface:python": (120, "ok", "healthy"),
            "surface:kubernetes": (1500, "ok", "too_wide"),
            "surface:react": (0, "ok", "zero"),
        }
        cts_bucket_overrides = {
            "surface:kubernetes": "too_wide",
            "surface:react": "zero",
            "surface:terraform": "zero",
            "surface:kafka": "stale",
            "surface:rails": "zero",
            "surface:js": "zero",
            "surface:nodejs": "zero",
            "surface:vue": "zero",
            "surface:aiops": "zero",
            "surface:llmops": "unknown",
        }
        for provider in ("boss", "cts", "liepin"):
            for surface_id, total, status, observed_at in cts_observations:
                if provider == "liepin":
                    total, status, bucket = liepin_overrides.get(
                        surface_id,
                        (total, status, "unknown" if status != "ok" else "healthy"),
                    )
                elif provider == "boss":
                    total, status, bucket = boss_overrides.get(
                        surface_id,
                        (total, status, "unknown" if status != "ok" else "healthy"),
                    )
                else:
                    bucket = cts_bucket_overrides.get(
                        surface_id, "unknown" if status != "ok" else "healthy"
                    )
                observation_id = f"obs:{provider}:{surface_id}"
                conn.execute(
                    """
                    insert into provider_recall_observations(
                      observation_id, provider, surface_id, query_text, query_hash,
                      query_mode, total, latency_ms, status, error_code, observed_at,
                      recall_bucket, provider_api_version, builder_run_id, evidence_ref
                    ) values (
                      ?, ?, ?, ?, ?, 'keyword', ?, 10, ?, null, ?, ?,
                      'fixture', 'fixture', ?
                    )
                    """,
                    (
                        observation_id,
                        provider,
                        surface_id,
                        surface_id.removeprefix("surface:"),
                        f"hash:{provider}:{surface_id}",
                        total,
                        status,
                        observed_at,
                        bucket,
                        f"fixture:{observation_id}",
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def open_test_snapshot(tmp_path: Path) -> SQLiteSnapshotStore:
    path = tmp_path / "snapshot.sqlite3"
    _make_snapshot(path)
    return SQLiteSnapshotStore.open(path)


@pytest.fixture
def snapshot_store(tmp_path: Path) -> SQLiteSnapshotStore:
    store = open_test_snapshot(tmp_path)
    try:
        yield store
    finally:
        store.close()
