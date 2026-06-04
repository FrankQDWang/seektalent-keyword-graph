# Quality Gate Schema

The graph quality gate must be machine-readable. Markdown summaries are useful,
but they are not enough to prove the production graph is ready.

## Required Artifact

Every production-candidate build must write a JSON quality gate artifact:

```text
artifacts/quality-gates/<builder_run_id>.quality-gate.json
```

`docs/readiness-report.md` must link this file and record its sha256.

## Top-Level Shape

The artifact must contain these top-level fields:

```json
{
  "schema_version": "keyword-graph-quality-gate-v1",
  "builder_run_id": "string",
  "snapshot_id": "string",
  "gate_status": "passed|failed|incomplete",
  "corpus": {},
  "surface_extraction": {},
  "relation_inference": {},
  "release_candidate_surfaces": {},
  "provider_observations": {},
  "query_recall_replay": {},
  "llm_candidates": {},
  "subagent_reviews": {},
  "manual_exceptions": [],
  "failures": [],
  "created_at": "ISO-8601 timestamp"
}
```

`gate_status` must be `failed` or `incomplete` if any required section is
missing.

## Required Metrics

### Corpus

Required fields:

- `manifest_path`;
- `corpus_id`;
- `corpus_version`;
- `expected_jd_count`;
- `actual_imported_jd_count`;
- `skipped_count`;
- `deduplicated_count`;
- `privacy_scan_status`;
- `clean_build_db`;
- `source_hash_policy`.

Fail or incomplete conditions:

- manifest missing;
- primary local corpus path missing;
- expected mainland count is not 9530 unless a newer manifest is explicitly
  documented;
- imported count differs from manifest without exclusion records;
- privacy scan did not run or found forbidden release data;
- build DB was reused from a previous run.

### Surface Extraction

Required fields:

- `total_candidate_mentions`;
- `accepted_surface_count`;
- `blocked_candidate_count`;
- `coverage_by_surface_type`;
- `coverage_by_section_type`;
- `high_frequency_rejects`;
- `ambiguous_surface_samples`;
- `generic_term_reject_samples`.

Fail or incomplete conditions:

- missing coverage by surface type;
- missing coverage by section type;
- accepted surface count is zero or obviously fixture-sized for the 9530-JD
  corpus;
- high-frequency generic rejects are not reported.

### Relation Inference

Required fields:

- `relation_count_by_type`;
- `confidence_distribution_by_type`;
- `alias_samples`;
- `abbreviation_samples`;
- `equivalent_samples`;
- `version_variant_samples`;
- `bad_merge_warnings`;
- `over_merge_warnings`.

Fail or incomplete conditions:

- relation count by type missing;
- confidence distribution missing;
- no merge samples for relation types that are present;
- bad merge warnings omitted from readiness evidence.

### Release Candidate Surfaces

Required fields:

- `extracted_surface_count`;
- `serving_surface_count`;
- `release_candidate_cts_surface_count`;
- `excluded_surface_count_by_reason`;
- `release_candidate_artifact_path`;
- `release_candidate_artifact_sha256`.

Fail or incomplete conditions:

- release candidate set missing;
- release candidate count is zero;
- release candidate count is suspiciously small relative to serving surfaces
  without a manual exception;
- excluded surfaces lack reason codes.

### Provider Observations

Required fields:

- `provider_sources`;
- `coverage_by_provider`;
- `coverage_by_query_mode`;
- `zero_count`;
- `too_wide_count`;
- `too_narrow_count`;
- `stale_count`;
- `unknown_count`;
- `real_cts_run_id`;
- `cts_gate_artifact_path`;
- `cts_gate_artifact_sha256`.

Fail or incomplete conditions:

- declared provider has no coverage report;
- final CTS observations are mock, fake, dry-run, fixture-derived, or missing;
- real CTS run lacks a gate artifact;
- partial CTS coverage is hidden instead of explicitly listed.

### Query Recall Replay

Required fields:

- `replay_case_count`;
- `provider_coverage`;
- `term_pool_cases`;
- `zero_recall_cases`;
- `too_wide_cases`;
- `unknown_cases`;
- `fallback_cases`;
- `failed_cases`.

Fail or incomplete conditions:

- no replay cases against the built snapshot;
- replay uses fixture snapshot instead of production-candidate snapshot;
- failed cases are omitted from the report.

### LLM Candidates

Required fields:

- `llm_provider`;
- `provider_endpoint_kind`;
- `model`;
- `prompt_version`;
- `candidate_count`;
- `accepted_count`;
- `rejected_count`;
- `pending_count`;
- `validation_method_distribution`.

Allowed `provider_endpoint_kind` values:

- `openai_compatible`;
- `disabled`.

The first intended LLM provider is Alibaba Cloud Bailian through an
OpenAI-compatible endpoint. The builder must treat all LLM credentials as
builder-only secrets.

Allowed candidate statuses:

- `pending`;
- `accepted`;
- `rejected`;
- `validated`.

Allowed validation sources:

- `human_review`;
- `golden_eval`;
- `rule_backed_evidence`;
- `provider_observation`.

Fail or incomplete conditions:

- accepted candidate lacks evidence span;
- accepted candidate lacks validation source;
- pending candidate enters snapshot projection;
- automatic validation accepts all candidates without rule-backed or eval-backed
  evidence.

### Subagent Reviews

Required fields:

- `graph_content_review_artifact`;
- `anti_hack_review_artifact`;
- `generalization_review_artifact`;
- `recall_readiness_review_artifact`;
- `blocking_findings_count`;
- `verdict`.

Fail or incomplete conditions:

- any required artifact missing;
- any review has blocking findings;
- artifact does not state clean-context review;
- readiness report does not link the review artifacts.

## Manual Exceptions

Manual exceptions are allowed only when they are explicit and auditable. Each
exception must include:

- `exception_id`;
- `metric`;
- `reason`;
- `approved_by`;
- `approved_at`;
- `expires_at`;
- `risk`;
- `follow_up`.

Free-text exceptions without these fields do not count.
