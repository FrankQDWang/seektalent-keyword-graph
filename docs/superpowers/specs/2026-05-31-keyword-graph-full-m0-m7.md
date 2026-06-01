# Keyword Graph Full First Version M0-M7 Spec

## Supersession

This spec supersedes `docs/superpowers/specs/2026-05-30-keyword-graph-m0-m7.md`
for implementation work. The 2026-05-30 implementation plan is retained only
as historical context and a negative example: its demo-oriented slices, fixed
fixture behavior, help-only CLI paths, empty responses, and incomplete builder
flow are not acceptable completion evidence for this spec.

The 2026-06-01 scope update adds SeekTalent Query Recall Optimization as a
first-version runtime requirement. `build_query_plan` remains supported, but
the runtime is incomplete unless it can also analyze and optimize existing
SeekTalent query term pools using provider-aware recall observations from the
local snapshot.

## Purpose

Build `seektalent-keyword-graph` into a complete first version of an independent
Python package and internal snapshot builder that turns public JD and historical
retrieval evidence into a versioned SQLite keyword graph snapshot and lets
SeekTalent consume that snapshot locally for deterministic query bundle
recommendations and provider-aware Query Recall Optimization.

Dependency direction is fixed:

```text
SeekTalent -> seektalent-keyword-graph package + SQLite snapshot
```

`seektalent-keyword-graph` must not import SeekTalent. Runtime code must not
import builder, CTS, or live provider modules.

## Non-Acceptance Contract

The implementation is not complete if any production path:

- returns fixed fixture data unrelated to build DB or snapshot contents;
- returns empty lists to satisfy an API shape while skipping real behavior;
- hard-codes only the terms used by tests;
- contains `TODO`, `NotImplementedError`, `pass` bodies, or unreachable code used
  as a substitute for behavior;
- exposes a CLI command that only prints help while claiming the command works;
- marks a milestone complete without an end-to-end test proving that milestone's
  data flow.

If a requirement cannot be implemented under the CTS/no-SeekTalent boundary, the
implementation plan must call it out as out of scope or blocked. It must not fake
the behavior.

## Product Boundary

The first version does:

- Import public or local JD JSONL into an internal SQLite build database with
  dedupe, source lineage, quality flags, and text references.
- Split JD text into sections with offsets and requirement strength signals.
- Extract keyword mentions using deterministic rules, seed dictionaries, and
  conservative n-gram candidates.
- Block or flag company-like, department-like, generic, and policy-blocked
  surfaces before they become query candidates.
- Normalize surfaces, compute surface statistics, cluster surfaces into concepts,
  build alias/abbreviation/translation/version relations, and persist evidence.
- Compute co-occurrence edges with support, Jaccard, and PMI-like scores.
- Generate CSV and JSONL sampling reports for high-risk surfaces and concept
  merges.
- Implement fake CTS and a real CTS count client tested only with mocked HTTP.
- Enforce CTS dry-run/default-safe behavior, real-probe gate, 09:00-21:00 window,
  max RPS, max concurrency, retry/backoff, TTL dedupe, and secret redaction.
- Build runtime SQLite snapshots from build DB state, including manifest and
  checksum artifacts.
- Validate snapshot schema, indexes, privacy boundaries, manifest/checksum,
  compressed size, replay behavior, and release readiness.
- Open snapshots read-only at runtime and produce deterministic
  `QueryPlanResponse` objects with concept sheet, query bundles, rejected
  surfaces, warnings, and lineage.
- Support all query bundle types as real selection behavior: `anchor`,
  `precision`, `alias_probe`, `exploration`, and `fallback`.
- Open the same snapshot after SeekTalent has already produced
  `RequirementSheet.initial_query_term_pool` or
  `RetrievalState.query_term_pool`, then analyze and optimize those query terms
  before SeekTalent calls CTS, Liepin, Boss, or later providers.
- Return provider-aware recall observations and graph-backed alternatives for
  each input query term without doing runtime network I/O.
- Support Query Recall Optimization actions that SeekTalent can apply to a term
  pool: keep, downrank, replace, add alias probe, add precision companion,
  mark score-only, or fallback.
- Provide SeekTalent-facing contract docs, JSON schemas, examples, failure mode
  documentation, and consumer tests.
- Build a wheel and prove package/runtime/builder import boundaries.

The first version does not:

- Build a UI, server, HTTP API, Docker runtime, Neo4j, PostgreSQL, Redis, Celery,
  or Kubernetes deployment.
- Require user-side CTS keys.
- Run user-side CTS, Liepin, Boss, or other provider probing.
- Call real CTS during unattended execution or CI.
- Store candidate lists, resume text, contact details, or candidate-level
  feedback.
- Modify the SeekTalent main project.
- Build company, industry, department, person, or candidate graphs.
- Replace SeekTalent's requirement extraction, retrieval orchestration, or
  candidate scoring pipeline.

## Naming

- Repository and Python distribution: `seektalent-keyword-graph`
- Python import package: `seektalent_keyword_graph`
- Public runtime class: `KeywordGraph`
- CLI command: `keyword-graph`
- SeekTalent runtime env prefix: `SEEKTALENT_KEYWORD_GRAPH_`
- Internal builder CTS env prefix: `KEYWORD_GRAPH_CTS_`
- Request schema: `query-plan-request-v1`
- Response schema: `query-plan-response-v1`
- Query recall request schema: `query-recall-request-v1`
- Query recall response schema: `query-recall-response-v1`
- Recall providers: provider strings such as `cts`, `liepin`, and `boss`;
  runtime contracts must treat provider as data, not as CTS-only code.
- Snapshot schema: `snapshot-v1`
- Selection policy: `policy-v1`

## Architecture

```text
contracts -> domain
runtime   -> contracts, domain, storage
engine    -> runtime, contracts
builder   -> contracts, domain, storage, cts
cli       -> builder and release validation commands
cts       -> httpx client, rate limit, fake/mocked probe behavior
```

Runtime constraints:

- opens SQLite snapshots using read-only URI mode;
- does not import `seektalent_keyword_graph.builder`;
- does not import `seektalent_keyword_graph.cts`;
- does not read `KEYWORD_GRAPH_CTS_*`;
- does not perform network I/O;
- does not write snapshot or global state;
- reads only provider recall observations already present in the local snapshot;
- supports provider-aware lookup for `cts`, `liepin`, `boss`, and future
  provider strings without importing provider clients.

Builder constraints:

- can read `KEYWORD_GRAPH_CTS_*` only inside CTS builder paths;
- defaults every CTS-capable command to dry-run or fake behavior;
- can run real CTS only with explicit `--real` plus a separate human gate and
  inside configured probe window;
- writes only aggregate provider totals and status into snapshots.

## Build Database Contract

The internal SQLite build DB must include these tables and indexes:

- `schema_migrations(version, applied_at)`
- `builder_runs(builder_run_id, started_at, finished_at, input_corpus_version, status, report_json)`
- `jd_documents(jd_id, source, source_ref, title_raw, jd_text_ref, jd_text, content_hash, language, captured_at, created_at, quality_flags_json)`
- `jd_sections(section_id, jd_id, section_type, text, start_offset, end_offset, confidence)`
- `keyword_mentions(mention_id, jd_id, section_id, surface_text_raw, surface_text_norm, mention_type, requirement_strength, evidence_text, start_offset, end_offset, extractor_name, extractor_version, confidence, review_status)`
- `blocked_surface_candidates(candidate_id, jd_id, section_id, surface_text_raw, surface_text_norm, reason_code, evidence_text, extractor_name)`
- `surfaces(surface_id, text_raw, text_norm, display_text, language, token_class, query_safe, is_exact_phrase_preferred, ambiguity_score, specificity_score, jd_df, jd_tf_total, serving_status, created_at, updated_at)`
- `concepts(concept_id, canonical_label, concept_type, description, primary_surface_id, surface_count, jd_df, stability_score, review_status, created_at, updated_at)`
- `concept_surfaces(concept_id, surface_id, confidence, source, status)`
- `surface_relations(relation_id, from_surface_id, to_surface_id, relation_type, confidence, evidence_type, created_by, status)`
- `cooccurrence_edges(edge_id, surface_id_a, surface_id_b, window_type, cooccur_count, pmi, jaccard, support, last_computed_at)`
- `probe_jobs(probe_job_id, provider, surface_id, query_text, query_hash, query_mode, priority, dedupe_key, scheduled_at, not_before, attempt_count, status, rate_limit_bucket, created_reason, last_error_code)`
- `provider_recall_observations(observation_id, provider, probe_job_id, surface_id, query_text, query_hash, query_mode, total, latency_ms, status, error_code, observed_at, recall_bucket, provider_api_version, builder_run_id, evidence_ref)`
- `review_decisions(decision_id, target_type, target_id, decision, reason, reviewer, reviewed_at)`
- `build_events(event_id, builder_run_id, event_type, message, payload_json, created_at)`

The build DB must be created by versioned SQL migrations, not ad hoc table
creation scattered through command handlers.

The canonical recall table is provider-aware. CTS is only the first provider
populating `provider_recall_observations`; schema, snapshot projection, runtime
lookup, contracts, and docs must not require a CTS-only table name or CTS-only
enum. A compatibility view may be added for older builder code during migration,
but final acceptance must read and validate provider rows through the canonical
provider-aware contract.

`surfaces.recall_bucket` is only the default serving bucket used by legacy query
bundle selection and must be derived deterministically from a documented default
provider policy. Query Recall Optimization must use
`provider_recall_observations.recall_bucket`, because one surface can be healthy
for `cts` and too-wide, stale, unknown, or unsupported for another provider.

## Runtime Snapshot Contract

The runtime SQLite snapshot must include these tables and indexes:

- `snapshot_meta(key, value)`
- `concepts`
- `surfaces`
- `concept_surfaces`
- `surface_relations`
- `cooccurrence_edges`
- `provider_recall_observations`
- `selection_policy_meta`
- optional `fts_surfaces` if FTS5 is available; runtime must work without FTS5
  by falling back to indexed normalized lookup.

Required `snapshot_meta` keys:

- `kg_snapshot_id`
- `snapshot_schema_version`
- `selection_policy_version`
- `built_at`
- `source_corpus_version`
- `builder_run_id`
- `build_report_sha256`
- `manifest_sha256`
- `provider_probe_window_start`
- `provider_probe_window_end`
- `provider_sources`
- `created_by_package_version`

Required indexes:

- `surfaces(text_norm)`
- `surfaces(recall_bucket, serving_status)`
- `concept_surfaces(concept_id)`
- `concept_surfaces(surface_id)`
- `surface_relations(from_surface_id, relation_type)`
- `surface_relations(to_surface_id, relation_type)`
- `cooccurrence_edges(surface_id_a)`
- `cooccurrence_edges(surface_id_b)`
- `provider_recall_observations(provider, surface_id, observed_at)`
- `provider_recall_observations(provider, query_hash, query_mode, observed_at)`

Snapshot validation must fail clearly for:

- missing file;
- unreadable or non-SQLite file;
- unsupported `snapshot_schema_version`;
- missing required table;
- missing required index;
- missing required meta key;
- orphan primary surface;
- concept/surface link pointing at missing rows;
- serving surface with no valid provider recall observation for at least one
  declared `provider_sources` provider unless explicitly marked stale/unknown by
  policy;
- forbidden secrets, candidate lists, resume text, or `.env` markers;
- compressed snapshot above 100MB.

## Runtime Query Planning Contract

`KeywordGraph.open(snapshot_path, manifest_path=None)` must:

- open the SQLite snapshot read-only;
- optionally verify external manifest checksum;
- validate schema, meta keys, indexes, and privacy markers;
- expose lookup helpers for surfaces and concepts;
- cache only read-only prepared data inside the engine instance.

`KeywordGraph.build_query_plan(request)` must:

- accept `QueryPlanRequest` Pydantic input;
- hash input deterministically into lineage;
- resolve concepts from requirement terms, JD text, title, and notes;
- expand candidate surfaces through concept membership and active relations;
- apply rejection policies before scoring;
- score surfaces using requirement strength, relation confidence, CTS recall
  bucket, specificity, ambiguity, freshness, and stability;
- build all applicable bundle types, respecting `max_query_bundles`;
- return fallback only when graph evidence is unavailable or unsafe, with warning
  codes and source terms;
- produce deterministic output for the same input and snapshot.

Bundle behavior:

- `anchor`: healthy or allowed-stale high-confidence surfaces from required or
  high-confidence preferred concepts.
- `precision`: too-wide surfaces paired with required companion terms or strong
  co-occurrence surfaces.
- `alias_probe`: zero, too-narrow, or stale primary surfaces with high-confidence
  alias/abbreviation/translation alternatives.
- `exploration`: safe unknown or emerging surfaces that have JD evidence but lack
  enough CTS confidence; low priority and explicitly marked exploration.
- `fallback`: title, notes, or incoming requirement terms used only when no graph
  route is trustworthy.

Rejected surfaces must include reason codes such as:

- `company_like`
- `department_like`
- `too_generic`
- `zero_recall`
- `too_wide_without_companion`
- `stale_observation`
- `low_confidence_alias`
- `policy_blocked`
- `no_active_concept`

## Runtime Query Recall Optimization Contract

`KeywordGraph.analyze_query_recall(request)` must:

- accept `QueryRecallRequest` Pydantic input with `request_id`, `provider`,
  either `query_text` or `query_terms`, default `query_mode`, and limits for
  alternatives and precision companions;
- reject unsupported providers with a typed contract/runtime error before any
  snapshot mutation or network action;
- normalize each input query, resolve it to active snapshot surfaces and concepts
  when possible, and preserve unmatched safe input queries in the response;
- return the selected provider recall observation for each input query:
  `provider`, `query_text`, `query_mode`, `total`, `status`, `observed_at`, and
  `recall_bucket`;
- distinguish matched-without-observation from no-match: the former has concept
  or surface provenance and an `unknown_observation` warning, while the latter
  has no graph match and a fallback/score-only recommendation;
- expand alternatives from same-concept surfaces and active relations with
  `relation_type` values such as `alias`, `abbreviation`, `equivalent`,
  `translation`, `normalized_form`, and `version_variant`;
- include relation/provenance fields for every candidate:
  `confidence`, `source_concept_id`, `source_surface_id`, `target_surface_id`,
  `evidence_type`, and `evidence_ref`;
- return provider recall observations for every alternative candidate when
  present, and mark missing observations as unknown without inventing totals;
- identify zero recall, too-wide recall, too-narrow recall, stale observation,
  and unknown observation using provider-specific policy thresholds from the
  snapshot;
- recommend concrete term-pool actions: `keep`, `downrank`, `replace`,
  `add_alias_probe`, `add_precision_companion`, `score_only`, or `fallback`;
- produce deterministic response ordering and lineage for the same input and
  snapshot.

`KeywordGraph.optimize_query_terms(request)` must:

- accept the same `QueryRecallRequest` or a validated dict;
- return `QueryRecallResponse` plus an ordered optimized term pool that
  SeekTalent can use to enhance or re-rank
  `RequirementSheet.initial_query_term_pool` or
  `RetrievalState.query_term_pool`;
- never remove the original term silently: replacements and downranking must be
  explicit actions with reasons and provider recall evidence;
- add alias probes only when graph relation confidence and provider recall
  evidence make the alternative safer than the original;
- add precision companions only when a too-wide original has a strong
  co-occurrence surface with healthier provider recall;
- mark `score_only` or `fallback` when graph evidence is absent or unsafe.

Runtime Query Recall Optimization must not:

- call CTS, Liepin, Boss, or any live provider;
- import builder, CTS, or provider client modules;
- read `KEYWORD_GRAPH_CTS_*` or any provider credential environment variable;
- hard-code CTS-only schema assumptions.

## Builder CLI Contract

These commands must perform real local work, not just show help:

```text
keyword-graph import-jds INPUT_JSONL --build-db build.sqlite3 --corpus-version fixture-v1
keyword-graph extract-surfaces --build-db build.sqlite3 --report out/extraction-report.json
keyword-graph build-relations --build-db build.sqlite3 --sampling-csv out/sampling.csv --sampling-jsonl out/sampling.jsonl
keyword-graph probe-cts --build-db build.sqlite3 --fake-response tests/fixtures/cts/fake_totals.json --dry-run
keyword-graph build-snapshot --build-db build.sqlite3 --snapshot out/kg.sqlite3 --manifest out/kg.manifest.json
keyword-graph validate-snapshot --snapshot out/kg.sqlite3 --manifest out/kg.manifest.json
```

CLI requirements:

- every command has tested `--help`;
- commands return non-zero on invalid inputs;
- import/extract/relation/probe/snapshot commands mutate the expected build DB or
  output files;
- `probe-cts` defaults to dry-run-safe behavior;
- `probe-cts --real` returns a gate error without a human-approved gate file;
- no command logs CTS tenant secret.

## CTS Probe Contract

Fake CTS must support:

- fixed success totals;
- zero recall;
- timeout;
- HTTP 429;
- HTTP 5xx;
- auth error;
- network error;
- request recording for retry, concurrency, and rate-limit assertions.

Real CTS client must be tested with mocked HTTP and must:

- send `page=1`, `pageSize=1`;
- read only `data.total`, status fields, and latency;
- classify timeout, 429, 5xx, auth, invalid query, and network errors;
- redact `tenant_secret` from `repr`, logs, reports, and exceptions;
- support configurable base URL, tenant key, timeout, API version, and trace id;
- use `httpx` only in builder/CTS code.

Probe runner must:

- require all real-probe gate inputs before any real CTS HTTP request:
  `probe-cts --real`, `--gate-file PATH`, gate file first line
  `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`, valid `KEYWORD_GRAPH_CTS_*`
  credentials, and current time inside the configured probe window;
- run mocked HTTP tests for the gated success path using a temporary gate file,
  never real network;
- enforce `KEYWORD_GRAPH_CTS_PROBE_MAX_RPS` default `1`;
- enforce `KEYWORD_GRAPH_CTS_PROBE_MAX_CONCURRENCY` default `1`;
- enforce `KEYWORD_GRAPH_CTS_PROBE_WINDOW_START=09:00`;
- enforce `KEYWORD_GRAPH_CTS_PROBE_WINDOW_END=21:00`;
- enforce timezone default `Asia/Shanghai`;
- implement TTL dedupe by query hash and query mode;
- retry timeout/429/5xx/network with bounded exponential backoff;
- stop scheduling after auth error;
- never overwrite a previous successful observation with a failure.

## Release Artifact Contract

`build-snapshot` and release validation must produce:

- runtime `.sqlite3`;
- compressed `.sqlite3.gz`;
- manifest JSON containing artifact names, byte sizes, sha256 checksums,
  `kg_snapshot_id`, schema versions, build time, source corpus version,
  builder run id, and policy version;
- build report JSON with input counts, extracted mention counts, blocked counts,
  relation counts, provider observation status counts, replay summary, privacy scan
  result, and validation status;
- release checklist and rollback instructions.

## SeekTalent Consumer Contract

The repository must include:

- `contracts/query-plan/request.example.json`
- `contracts/query-plan/response.example.json`
- `contracts/query-plan/query-plan-request.schema.json`
- `contracts/query-plan/query-plan-response.schema.json`
- `contracts/query-recall/request.example.json`
- `contracts/query-recall/response.example.json`
- `contracts/query-recall/query-recall-request.schema.json`
- `contracts/query-recall/query-recall-response.schema.json`
- `docs/seektalent-integration.md`
- `docs/query-recall-optimization.md`
- `tests/contract/test_consumer_contract.py`

Integration docs must cover:

- `SEEKTALENT_KEYWORD_GRAPH_ENABLED`
- `SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH`
- `SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID`
- `SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN`
- `SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES`
- `SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER`
- `SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES`
- `keyword_graph_unavailable` failure mode;
- where `analyze_query_recall` and `optimize_query_terms` run in the SeekTalent
  flow between query term pool generation and provider retrieval;
- no user-side CTS key;
- no SeekTalent main-project modification in this repo.

## Testing Requirements

Acceptance tests must cover:

- package import and wheel install smoke;
- Pydantic request/response contract and generated JSON schemas;
- build DB migrations and table/index presence;
- JD JSONL import with dedupe, quality flags, and bad-record reporting;
- section offsets and requirement strength detection;
- extraction mentions with JD/section/evidence lineage;
- company/department/generic blocking;
- extraction report content;
- surface normalization for full-width, mixed case, symbols, Chinese/English,
  whitespace, and version tokens;
- concept clustering that merges `k8s`/`Kubernetes` only with evidence and does
  not merge unrelated peer frameworks such as `Vue`/`React`;
- relation persistence with evidence and confidence;
- co-occurrence persistence with deterministic support/Jaccard/PMI values;
- sampling CSV/JSONL generation;
- fake CTS status coverage;
- mocked real CTS payload, parsing, error handling, retry, rate limit,
  concurrency, window, TTL, and secret redaction;
- snapshot build from build DB, manifest, checksum, privacy scan, and validation;
- runtime snapshot negative cases;
- query bundle behavior for anchor, precision, alias_probe, exploration, and
  fallback;
- Query Recall Optimization contract behavior for single query lookup, multiple
  query-term pool optimization, alias/equivalent/normalized expansion,
  unsupported provider, query no match, matched query with no observation, zero
  recall, too-wide recall, stale observation, unknown observation, and provider
  distinction across `cts`, `liepin`, and `boss` fixture rows;
- full integration flow: JD fixture -> build DB -> snapshot -> `KeywordGraph.open`
  -> `build_query_plan`;
- full integration flow: fixture build DB -> provider-aware snapshot ->
  `KeywordGraph.open` -> query term pool input -> `optimize_query_terms`;
- all CLI commands executing local fixture flow;
- runtime/builder/CTS/SeekTalent import boundaries;
- old-name scan;
- readiness report accuracy.

## Milestones

### M0: Project Foundation

Acceptance:

- `uv sync --extra dev --extra builder` succeeds.
- `uv run pytest --version`, `uv run ruff --version`, and
  `uv run python -m build --version` succeed.
- `uv run python -c "import pydantic, httpx"` succeeds.
- Package metadata name is `seektalent-keyword-graph`.
- Package import succeeds from source and from built wheel.
- No CTS client is reachable from runtime import paths.
- No real CTS call exists in tests or default CLI behavior.

### M1: Runtime Contracts and Snapshot Reader

Acceptance:

- Typed Pydantic contracts validate examples and generate JSON schemas.
- Read-only snapshot open succeeds for a valid fixture.
- Manifest checksum validation succeeds and fails on mismatch.
- Missing, unsupported, corrupt, incomplete, or privacy-violating snapshots raise
  typed errors.
- Lookup APIs return concepts, surfaces, relations, recall summaries, and
  alternatives from snapshot data.
- Query Recall Optimization contracts validate provider-aware examples and
  generated JSON schemas.
- Runtime import and environment tests prove no builder/CTS import and no CTS env
  read.

### M2: JD Import and Keyword Extraction

Acceptance:

- Fixture JSONL imports into build DB with dedupe and bad-record report.
- JD sections persist with offsets and section type.
- Mentions persist with JD/section/evidence lineage and requirement strength.
- Company-like, department-like, generic, and blocked policy terms are persisted
  as blocked candidates, not serving surfaces.
- Extraction report includes counts, top surfaces, blocked reason summary, and
  failed records.
- `keyword-graph import-jds` and `keyword-graph extract-surfaces` run against
  local fixtures and write expected DB/report artifacts.

### M3: Surface, Concept, Relation, Co-occurrence

Acceptance:

- Surface normalization, language classification, token class, specificity, and
  ambiguity are persisted.
- Concept clustering creates stable concept IDs from normalized evidence.
- Alias evidence merges `k8s` and `Kubernetes`; weak evidence does not merge
  `Vue` and `React`.
- Relations persist with confidence, evidence type, status, and created_by.
- Co-occurrence edges persist with support, Jaccard, and PMI-like values.
- Sampling CSV and JSONL are generated with risk reasons and review targets.
- `keyword-graph build-relations` runs against a fixture build DB and writes
  relation/co-occurrence/sampling outputs.

### M4: Internal CTS Count Probe

Acceptance:

- Fake CTS covers success, zero, timeout, 429, 5xx, auth, and network error.
- Real CTS client has complete mocked HTTP tests and never calls the network in
  CI.
- Probe runner enforces RPS, concurrency, time window, TTL dedupe, retry/backoff,
  and auth pause.
- `probe-cts --dry-run` writes planned jobs/payloads or fake observations without
  touching real CTS.
- `probe-cts --real` fails closed unless `--gate-file` exists, contains
  `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`, credentials are present, and the current
  time is inside the configured window; gated success is covered only with mocked
  HTTP.
- Runtime package does not import CTS code and does not read CTS env.
- Probe persistence writes provider-aware rows with `provider='cts'`; runtime
  does not depend on a CTS-only recall table.

### M5: Snapshot Build, Query Bundles, and Query Recall Optimization

Acceptance:

- Snapshot builder projects build DB contents into all required runtime tables and
  indexes, including `provider_recall_observations`.
- Snapshot manifest/checksum/build report are generated.
- Snapshot validation rejects schema, referential, privacy, checksum, and size
  failures.
- Runtime query planner emits real anchor, precision, alias_probe, exploration,
  and fallback bundles when fixture evidence calls for each type.
- Runtime `analyze_query_recall` and `optimize_query_terms` emit provider-aware
  input observations, graph alternatives, relation provenance, recall warnings,
  and term-pool actions for fixture evidence.
- Runtime query recall behavior distinguishes unsupported provider, no match,
  matched-without-observation, zero recall, too-wide recall, stale observation,
  unknown observation, and multiple provider rows.
- Response includes concept sheet, reason codes, rejected surfaces, warnings, and
  lineage with input hash and policy version.
- Replay evaluation report is generated and includes bundle counts, warning
  counts, rejected reason counts, query recall action counts, provider
  observation status counts, and stability checks.
- Integration flow from JD fixture to runtime response passes.

### M6: SeekTalent Integration Contract

Acceptance:

- Contract examples and JSON schemas are stable and validated.
- Consumer tests demonstrate how SeekTalent would load config, call the package,
  and fail open with `keyword_graph_unavailable`.
- Docs define `SEEKTALENT_KEYWORD_GRAPH_*` env vars and no-CTS-user boundary.
- Docs show where Query Recall Optimization fits between SeekTalent query term
  pool generation and provider retrieval, with example request/response for
  `optimize_query_terms`.
- No SeekTalent main-project files are modified.

### M7: Release Hardening

Acceptance:

- Wheel builds and wheel install smoke passes.
- Artifact validation checks compressed size, manifest, checksum, secret markers,
  candidate markers, resume markers, and old names.
- CLI fixture flow runs end-to-end.
- Import-boundary tests cover runtime, domain, builder, CTS, and SeekTalent.
- Release checklist, rollback instructions, and readiness report exist.
- `docs/readiness-report.md` maps every M0-M7 acceptance item to fresh test or
  command evidence, separately lists Query Recall Optimization status, lists
  incomplete items explicitly, and includes current HEAD.

## Completion Standard

Before marking the goal complete, run fresh:

```bash
uv sync --extra dev --extra builder
uv run pytest
uv run ruff check .
uv run python -m build --wheel
uv run pytest tests/architecture/test_import_boundaries.py -q
rg -n "seektalent-keyword-intel|seektalent_keyword_intel|KEYWORD_INTEL|keyword_intelligence" \
  README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts docs
uv run pytest tests/integration/test_cli_end_to_end.py -q
uv run pytest tests/integration/test_query_recall_optimization.py -q
keyword-graph validate-snapshot --snapshot <fixture-built-snapshot> --manifest <fixture-manifest>
```

The old-name `rg` command must exit 1 with no matches. Every other command must
exit 0. `docs/readiness-report.md` must be regenerated after these commands.
