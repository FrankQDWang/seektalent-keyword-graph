"""Authoritative SQLite schema definitions for build and runtime databases."""

# ruff: noqa: E501

from __future__ import annotations

BUILD_SCHEMA_VERSION = "build-v1"
SNAPSHOT_SCHEMA_VERSION = "snapshot-v1"
SELECTION_POLICY_VERSION = "policy-v1"

BUILD_TABLES = {
    "schema_migrations",
    "builder_runs",
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
    "review_decisions",
    "build_events",
}

BUILD_INDEXES = {
    "idx_build_jd_documents_content_hash",
    "idx_build_jd_sections_jd_id",
    "idx_build_keyword_mentions_jd_id",
    "idx_build_keyword_mentions_surface_text_norm",
    "idx_build_blocked_surface_candidates_jd_id",
    "idx_build_surfaces_text_norm",
    "idx_build_surfaces_serving_status",
    "idx_build_concepts_primary_surface_id",
    "idx_build_concept_surfaces_concept_id",
    "idx_build_concept_surfaces_surface_id",
    "idx_build_surface_relations_from_type",
    "idx_build_surface_relations_to_type",
    "idx_build_cooccurrence_edges_surface_a",
    "idx_build_cooccurrence_edges_surface_b",
    "idx_build_probe_jobs_surface_id",
    "idx_build_probe_jobs_provider_query",
    "idx_build_probe_jobs_dedupe_key",
    "idx_build_provider_observations_surface_observed",
    "idx_build_provider_observations_query_observed",
    "idx_build_review_decisions_target",
    "idx_build_events_builder_run_id",
}

SNAPSHOT_TABLES = {
    "snapshot_meta",
    "concepts",
    "surfaces",
    "concept_surfaces",
    "surface_relations",
    "cooccurrence_edges",
    "provider_recall_observations",
    "selection_policy_meta",
}

SNAPSHOT_INDEXES = {
    "idx_snapshot_surfaces_text_norm",
    "idx_snapshot_surfaces_recall_serving",
    "idx_snapshot_concept_surfaces_concept_id",
    "idx_snapshot_concept_surfaces_surface_id",
    "idx_snapshot_surface_relations_from_type",
    "idx_snapshot_surface_relations_to_type",
    "idx_snapshot_cooccurrence_edges_surface_a",
    "idx_snapshot_cooccurrence_edges_surface_b",
    "idx_snapshot_provider_observations_surface_observed",
    "idx_snapshot_provider_observations_query_observed",
}

REQUIRED_SNAPSHOT_META_KEYS = {
    "kg_snapshot_id",
    "snapshot_schema_version",
    "selection_policy_version",
    "built_at",
    "source_corpus_version",
    "builder_run_id",
    "build_report_sha256",
    "manifest_sha256",
    "provider_probe_window_start",
    "provider_probe_window_end",
    "provider_sources",
    "cts_probe_window_start",
    "cts_probe_window_end",
    "created_by_package_version",
}

BUILD_SCHEMA_SQL = """
create table if not exists schema_migrations (
  version text primary key,
  applied_at text not null default current_timestamp
);

create table if not exists builder_runs (
  builder_run_id text primary key,
  started_at text not null,
  finished_at text,
  input_corpus_version text not null,
  status text not null,
  report_json text not null
);

create table if not exists jd_documents (
  jd_id text primary key,
  source text not null,
  source_ref text not null,
  title_raw text not null,
  jd_text_ref text not null,
  jd_text text not null,
  content_hash text not null,
  language text not null,
  captured_at text not null,
  created_at text not null,
  quality_flags_json text not null
);

create table if not exists jd_sections (
  section_id text primary key,
  jd_id text not null references jd_documents(jd_id),
  section_type text not null,
  text text not null,
  start_offset integer not null,
  end_offset integer not null,
  confidence real not null
);

create table if not exists keyword_mentions (
  mention_id text primary key,
  jd_id text not null references jd_documents(jd_id),
  section_id text not null references jd_sections(section_id),
  surface_text_raw text not null,
  surface_text_norm text not null,
  mention_type text not null,
  requirement_strength text not null,
  evidence_text text not null,
  start_offset integer not null,
  end_offset integer not null,
  extractor_name text not null,
  extractor_version text not null,
  confidence real not null,
  review_status text not null
);

create table if not exists blocked_surface_candidates (
  candidate_id text primary key,
  jd_id text not null references jd_documents(jd_id),
  section_id text not null references jd_sections(section_id),
  surface_text_raw text not null,
  surface_text_norm text not null,
  reason_code text not null,
  evidence_text text not null,
  extractor_name text not null
);

create table if not exists surfaces (
  surface_id text primary key,
  text_raw text not null,
  text_norm text not null unique,
  display_text text not null,
  language text not null,
  token_class text not null,
  query_safe integer not null,
  is_exact_phrase_preferred integer not null,
  ambiguity_score real not null,
  specificity_score real not null,
  jd_df integer not null,
  jd_tf_total integer not null,
  recall_bucket text not null default 'unknown',
  serving_status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists concepts (
  concept_id text primary key,
  canonical_label text not null,
  concept_type text not null,
  description text not null,
  primary_surface_id text references surfaces(surface_id),
  surface_count integer not null,
  jd_df integer not null,
  stability_score real not null,
  review_status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists concept_surfaces (
  concept_id text not null references concepts(concept_id),
  surface_id text not null references surfaces(surface_id),
  confidence real not null,
  source text not null,
  status text not null,
  primary key (concept_id, surface_id)
);

create table if not exists surface_relations (
  relation_id text primary key,
  from_surface_id text not null references surfaces(surface_id),
  to_surface_id text not null references surfaces(surface_id),
  relation_type text not null,
  confidence real not null,
  evidence_type text not null,
  created_by text not null,
  status text not null
);

create table if not exists cooccurrence_edges (
  edge_id text primary key,
  surface_id_a text not null references surfaces(surface_id),
  surface_id_b text not null references surfaces(surface_id),
  window_type text not null,
  cooccur_count integer not null,
  pmi real not null,
  jaccard real not null,
  support real not null,
  last_computed_at text not null
);

create table if not exists probe_jobs (
  probe_job_id text primary key,
  provider text not null,
  surface_id text not null references surfaces(surface_id),
  query_text text not null,
  query_hash text not null,
  query_mode text not null,
  priority integer not null,
  dedupe_key text not null unique,
  scheduled_at text not null,
  not_before text not null,
  attempt_count integer not null,
  status text not null,
  rate_limit_bucket text not null,
  created_reason text not null,
  last_error_code text
);

create table if not exists provider_recall_observations (
  observation_id text primary key,
  probe_job_id text not null references probe_jobs(probe_job_id),
  provider text not null,
  surface_id text not null references surfaces(surface_id),
  query_text text not null,
  query_hash text not null,
  query_mode text not null,
  total integer,
  latency_ms integer,
  status text not null,
  error_code text,
  observed_at text not null,
  recall_bucket text not null,
  provider_api_version text not null,
  builder_run_id text not null references builder_runs(builder_run_id),
  evidence_ref text
);

create table if not exists review_decisions (
  decision_id text primary key,
  target_type text not null,
  target_id text not null,
  decision text not null,
  reason text not null,
  reviewer text not null,
  reviewed_at text not null
);

create table if not exists build_events (
  event_id text primary key,
  builder_run_id text not null references builder_runs(builder_run_id),
  event_type text not null,
  message text not null,
  payload_json text not null,
  created_at text not null
);

create index if not exists idx_build_jd_documents_content_hash on jd_documents(content_hash);
create index if not exists idx_build_jd_sections_jd_id on jd_sections(jd_id);
create index if not exists idx_build_keyword_mentions_jd_id on keyword_mentions(jd_id);
create index if not exists idx_build_keyword_mentions_surface_text_norm on keyword_mentions(surface_text_norm);
create index if not exists idx_build_blocked_surface_candidates_jd_id on blocked_surface_candidates(jd_id);
create index if not exists idx_build_surfaces_text_norm on surfaces(text_norm);
create index if not exists idx_build_surfaces_serving_status on surfaces(serving_status);
create index if not exists idx_build_concepts_primary_surface_id on concepts(primary_surface_id);
create index if not exists idx_build_concept_surfaces_concept_id on concept_surfaces(concept_id);
create index if not exists idx_build_concept_surfaces_surface_id on concept_surfaces(surface_id);
create index if not exists idx_build_surface_relations_from_type on surface_relations(from_surface_id, relation_type);
create index if not exists idx_build_surface_relations_to_type on surface_relations(to_surface_id, relation_type);
create index if not exists idx_build_cooccurrence_edges_surface_a on cooccurrence_edges(surface_id_a);
create index if not exists idx_build_cooccurrence_edges_surface_b on cooccurrence_edges(surface_id_b);
create index if not exists idx_build_probe_jobs_surface_id on probe_jobs(surface_id);
create index if not exists idx_build_probe_jobs_provider_query on probe_jobs(provider, query_hash, query_mode);
create index if not exists idx_build_probe_jobs_dedupe_key on probe_jobs(dedupe_key);
create index if not exists idx_build_provider_observations_surface_observed on provider_recall_observations(provider, surface_id, observed_at);
create index if not exists idx_build_provider_observations_query_observed on provider_recall_observations(provider, query_hash, query_mode, observed_at);
create index if not exists idx_build_review_decisions_target on review_decisions(target_type, target_id);
create index if not exists idx_build_events_builder_run_id on build_events(builder_run_id);
"""

RUNTIME_SNAPSHOT_SCHEMA_SQL = """
create table if not exists snapshot_meta (
  key text primary key,
  value text not null
);

create table if not exists surfaces (
  surface_id text primary key,
  text_raw text not null,
  text_norm text not null unique,
  display_text text not null,
  language text not null,
  token_class text not null,
  query_safe integer not null,
  is_exact_phrase_preferred integer not null,
  ambiguity_score real not null,
  specificity_score real not null,
  jd_df integer not null,
  jd_tf_total integer not null,
  recall_bucket text not null,
  serving_status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists concepts (
  concept_id text primary key,
  canonical_label text not null,
  concept_type text not null,
  description text not null,
  primary_surface_id text references surfaces(surface_id),
  surface_count integer not null,
  jd_df integer not null,
  stability_score real not null,
  review_status text not null,
  created_at text not null,
  updated_at text not null
);

create table if not exists concept_surfaces (
  concept_id text not null references concepts(concept_id),
  surface_id text not null references surfaces(surface_id),
  confidence real not null,
  source text not null,
  status text not null,
  primary key (concept_id, surface_id)
);

create table if not exists surface_relations (
  relation_id text primary key,
  from_surface_id text not null references surfaces(surface_id),
  to_surface_id text not null references surfaces(surface_id),
  relation_type text not null,
  confidence real not null,
  evidence_type text not null,
  created_by text not null,
  status text not null
);

create table if not exists cooccurrence_edges (
  edge_id text primary key,
  surface_id_a text not null references surfaces(surface_id),
  surface_id_b text not null references surfaces(surface_id),
  window_type text not null,
  cooccur_count integer not null,
  pmi real not null,
  jaccard real not null,
  support real not null,
  last_computed_at text not null
);

create table if not exists provider_recall_observations (
  observation_id text primary key,
  provider text not null,
  surface_id text not null references surfaces(surface_id),
  query_text text not null,
  query_hash text not null,
  query_mode text not null,
  total integer,
  latency_ms integer,
  status text not null,
  error_code text,
  observed_at text not null,
  recall_bucket text not null,
  provider_api_version text not null,
  builder_run_id text not null,
  evidence_ref text
);

create table if not exists selection_policy_meta (
  key text primary key,
  value text not null
);

create index if not exists idx_snapshot_surfaces_text_norm on surfaces(text_norm);
create index if not exists idx_snapshot_surfaces_recall_serving on surfaces(recall_bucket, serving_status);
create index if not exists idx_snapshot_concept_surfaces_concept_id on concept_surfaces(concept_id);
create index if not exists idx_snapshot_concept_surfaces_surface_id on concept_surfaces(surface_id);
create index if not exists idx_snapshot_surface_relations_from_type on surface_relations(from_surface_id, relation_type);
create index if not exists idx_snapshot_surface_relations_to_type on surface_relations(to_surface_id, relation_type);
create index if not exists idx_snapshot_cooccurrence_edges_surface_a on cooccurrence_edges(surface_id_a);
create index if not exists idx_snapshot_cooccurrence_edges_surface_b on cooccurrence_edges(surface_id_b);
create index if not exists idx_snapshot_provider_observations_surface_observed on provider_recall_observations(provider, surface_id, observed_at);
create index if not exists idx_snapshot_provider_observations_query_observed on provider_recall_observations(provider, query_hash, query_mode, observed_at);
"""
