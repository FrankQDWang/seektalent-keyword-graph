# Keyword Graph Full First Version M0-M7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete first version of `seektalent-keyword-graph`: an installable runtime package plus internal builder pipeline that imports JD fixtures, extracts keyword evidence, builds a SQLite snapshot with CTS recall summaries, and returns deterministic SeekTalent query bundles.

**Architecture:** The package has a hard runtime/builder split. Runtime reads a validated readonly SQLite snapshot and performs local concept resolution, surface selection, and bundle building. Builder commands create build DB state from JD fixtures, derive graph evidence, run fake or explicitly gated CTS probe flows, build/validate snapshot artifacts, and produce release reports.

**Tech Stack:** Python 3.12+, uv, hatchling, Pydantic v2, SQLite, httpx for builder-only CTS HTTP, pytest, ruff, JSONL, CSV, gzip, sha256 manifests.

**Linked Spec:** `docs/superpowers/specs/2026-05-31-keyword-graph-full-m0-m7.md`

---

## Planning Status

This plan supersedes the 2026-05-30 S0-S19 plan for build execution. The old plan is not an approved build input because it allows incomplete runtime behavior, fixed fixture shortcuts, help-only CLI paths, and empty/constant outputs. This plan is intentionally larger because the requested deliverable is a complete first version, not a demo slice.

## Selected Execution Mode

When this plan reaches `fw-build`, execution will use
`superpowers:subagent-driven-development`: a fresh worker per task, followed by
spec-compliance review and code-quality review before moving to the next task.
Tasks remain sequential at the plan level so build DB, schema, and CLI flows are
not corrupted by overlapping writes.

## Execution Rules

- Execute tasks in order.
- Each task starts with acceptance-level tests or command-level fixture flow before production code.
- Watch the new tests fail for the right reason.
- Implement the complete behavior required for that task; do not use fixed fixture branches or empty outputs.
- Run the task's listed green verification.
- Commit each verified task separately.
- Do not call real CTS during unattended execution.
- Real CTS requires a future explicit human gate; mocked HTTP and fake CTS are the only automated CTS paths.
- Runtime code must not import `seektalent_keyword_graph.builder` or `seektalent_keyword_graph.cts`.
- This package must not import SeekTalent or modify the SeekTalent main project.
- If an acceptance item cannot be implemented under these boundaries, stop and update the plan/readiness report instead of faking it.

## File Map

### Project and Quality

- `pyproject.toml`: package metadata, dependencies, script entry point, ruff/pytest config.
- `Makefile`: `sync`, `test`, `lint`, `build-wheel`, `check`, `fixture-flow`.
- `.python-version`: Python 3.12.
- `.env.example`: documents builder-only CTS env names without secrets.

### Public Package

- `src/seektalent_keyword_graph/__init__.py`: exports `KeywordGraph`, `QueryPlanRequest`, `QueryPlanResponse`, errors, and version.
- `src/seektalent_keyword_graph/engine.py`: public runtime facade; delegates to runtime components only.
- `src/seektalent_keyword_graph/config.py`: runtime `SEEKTALENT_KEYWORD_GRAPH_*` config model only; no CTS env reads.
- `src/seektalent_keyword_graph/cli.py`: real local CLI dispatch for builder/release flows.

### Contracts

- `src/seektalent_keyword_graph/contracts/query_plan.py`: Pydantic request/response and nested query models.
- `src/seektalent_keyword_graph/contracts/snapshot.py`: snapshot manifest and meta Pydantic models.
- `contracts/query-plan/*.json`: examples and generated JSON schemas.
- `docs/query-plan-contract.md`: field semantics and compatibility rules.

### Domain

- `src/seektalent_keyword_graph/domain/models.py`: dataclasses/enums for concepts, surfaces, mentions, relations, observations, bundles.
- `src/seektalent_keyword_graph/domain/normalization.py`: Unicode/case/spacing/version normalization.
- `src/seektalent_keyword_graph/domain/classification.py`: language, token class, company/department/generic heuristics.
- `src/seektalent_keyword_graph/domain/scoring.py`: recall bucket, serving score, freshness, ambiguity/specificity scoring.
- `src/seektalent_keyword_graph/domain/policies.py`: rejection reasons and bundle eligibility.

### Storage

- `src/seektalent_keyword_graph/storage/sqlite_schema.py`: versioned SQL strings for build DB and runtime snapshot.
- `src/seektalent_keyword_graph/storage/sqlite_migrations.py`: migration runner and schema inspection.
- `src/seektalent_keyword_graph/storage/privacy_scan.py`: byte/string marker scan for forbidden release data.

### Runtime

- `src/seektalent_keyword_graph/runtime/errors.py`: typed runtime/snapshot errors.
- `src/seektalent_keyword_graph/runtime/snapshot_store.py`: readonly SQLite adapter and manifest validation.
- `src/seektalent_keyword_graph/runtime/concept_resolver.py`: request terms/JD text/notes to concept candidates.
- `src/seektalent_keyword_graph/runtime/surface_selector.py`: expansion, rejection, scoring, deterministic ranking.
- `src/seektalent_keyword_graph/runtime/bundle_builder.py`: anchor/precision/alias_probe/exploration/fallback bundle assembly.
- `src/seektalent_keyword_graph/runtime/query_planner.py`: orchestrates runtime planning and lineage.

### Builder

- `src/seektalent_keyword_graph/builder/build_store.py`: SQLite build DB adapter.
- `src/seektalent_keyword_graph/builder/import_jds.py`: JSONL import, dedupe, quality flags.
- `src/seektalent_keyword_graph/builder/sections.py`: JD section splitting with offsets and strength hints.
- `src/seektalent_keyword_graph/builder/extractors.py`: deterministic surface extraction pipeline.
- `src/seektalent_keyword_graph/builder/extract_surfaces.py`: persists mentions, surfaces, blocked candidates, report.
- `src/seektalent_keyword_graph/builder/build_relations.py`: concept clustering, alias evidence, relation persistence.
- `src/seektalent_keyword_graph/builder/cooccurrence.py`: co-occurrence metrics and persistence.
- `src/seektalent_keyword_graph/builder/sampling_report.py`: CSV/JSONL risk report generation.
- `src/seektalent_keyword_graph/builder/cts_probe.py`: probe job scheduling and fake/dry-run observation persistence.
- `src/seektalent_keyword_graph/builder/build_snapshot.py`: projects build DB to runtime snapshot and artifacts.
- `src/seektalent_keyword_graph/builder/validate_snapshot.py`: schema, referential, privacy, replay, size validation.

### CTS

- `src/seektalent_keyword_graph/cts/config.py`: builder-only CTS config from `KEYWORD_GRAPH_CTS_*`.
- `src/seektalent_keyword_graph/cts/fake_client.py`: fake count client with request recording and error simulation.
- `src/seektalent_keyword_graph/cts/count_client.py`: httpx count-only client, mocked in tests.
- `src/seektalent_keyword_graph/cts/rate_limit.py`: async token bucket and concurrency gate.
- `src/seektalent_keyword_graph/cts/probe_window.py`: timezone-aware real-probe window/gate.
- `src/seektalent_keyword_graph/cts/retry.py`: retry/backoff classification.

### Observability, Release, and Docs

- `src/seektalent_keyword_graph/observability/build_report.py`: build/extraction/replay summary generation.
- `src/seektalent_keyword_graph/observability/replay_report.py`: replay case summaries and stability checks.
- `src/seektalent_keyword_graph/release_validation.py`: manifest/checksum/size/privacy artifact checks.
- `scripts/run_fixture_flow.py`: local end-to-end fixture flow used by tests and readiness.
- `scripts/write_readiness_report.py`: command-derived readiness report writer.
- `docs/seektalent-integration.md`: consumer config, failure mode, artifacts, fail-open behavior.
- `docs/snapshot-schema.md`: runtime/build schema reference.
- `docs/cts-offline-probe.md`: CTS dry-run, mock, gate, and real-probe policy.
- `docs/release-checklist.md`: release gate checklist.
- `docs/runbooks/rollback-snapshot.md`: package/snapshot rollback instructions.
- `docs/readiness-report.md`: final evidence report.

### Tests and Fixtures

- `tests/unit/`: domain, scoring, extraction, CTS, release unit tests.
- `tests/contract/`: Pydantic examples, JSON schema, consumer contract tests.
- `tests/snapshot/`: schema and bad snapshot tests.
- `tests/builder/`: import/extract/relation/probe/snapshot builder tests.
- `tests/runtime/`: snapshot store, resolver, selector, bundle builder, query planner tests.
- `tests/integration/`: CLI fixture flow and JD-to-runtime end-to-end tests.
- `tests/architecture/`: import boundaries, no SeekTalent import, no runtime CTS env read.
- `tests/fixtures/jds/`: small JSONL corpus covering anchor, precision, alias, exploration, fallback, blocked terms.
- `tests/fixtures/cts/`: fake totals and mocked HTTP responses.

## Task Checklist

| Task | Milestone | Outcome |
| --- | --- | --- |
| T0 | M0 | Project foundation and anti-shortcut guards |
| T1 | M1 | Public contracts, schemas, and examples |
| T2 | M1/M5 | SQLite schema, migrations, and build/runtime stores |
| T3 | M2 | JD import, sectioning, and extraction report |
| T4 | M3 | Surface normalization, classification, concepts, and alias evidence |
| T5 | M3 | Co-occurrence persistence and sampling reports |
| T6 | M4 | Fake CTS and mocked real CTS client |
| T7 | M4 | Probe jobs, rate limit, window, TTL, retry, dry-run observations |
| T8 | M5 | Snapshot build, manifest, checksum, validation |
| T9 | M5 | Runtime resolver, selector, bundle builder, query planner |
| T10 | M2-M5 | Real local CLI command flows |
| T11 | M5 | Replay evaluation and full JD-to-runtime integration |
| T12 | M6 | SeekTalent consumer contracts and docs |
| T13 | M7 | Release hardening, import boundaries, wheel smoke |
| T14 | M7 | Readiness report and final verification |

---

### Task T0: Project Foundation and Anti-Shortcut Guards

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.python-version`
- Create: `.env.example`
- Create: `tests/architecture/test_no_shortcuts.py`
- Create: `tests/architecture/test_import_boundaries.py`

- [ ] **Step 1: Write architecture guard tests**

Create tests that scan `src/` for blocked implementation markers in production
Python files and assert runtime/domain import boundaries before source files
exist. The guard must allow docs and tests to mention blocked words, but must
fail on production `pass` statement bodies, `NotImplementedError`, and modules
that import SeekTalent.

Run:

```bash
uv run pytest tests/architecture/test_no_shortcuts.py tests/architecture/test_import_boundaries.py -q
```

Expected: FAIL because package/config/source tree is not created.

- [ ] **Step 2: Create package scaffold and quality config**

Create `pyproject.toml` with:

- package name `seektalent-keyword-graph`;
- Python `>=3.12`;
- dependencies `pydantic>=2.7`;
- builder extra `httpx>=0.27`;
- dev extra `build`, `pytest`, `ruff`;
- script `keyword-graph = "seektalent_keyword_graph.cli:main"`;
- hatchling package path `src/seektalent_keyword_graph`;
- ruff select `E,F,I,UP,B,SIM,C4,PIE,PT`;
- pytest paths `tests`.

Create `.python-version`, `.env.example`, and `Makefile` targets:

```makefile
sync:
	uv sync --extra dev --extra builder

test:
	uv run pytest

lint:
	uv run ruff check .

build-wheel:
	uv run python -m build --wheel

check: lint test build-wheel
```

- [ ] **Step 3: Add empty package modules with real import surfaces only**

Create `src/seektalent_keyword_graph/__init__.py`, `engine.py`, and `cli.py`
only to expose imports and a parser entry point. These files may not include
business behavior beyond package metadata and command parser construction.

- [ ] **Step 4: Verify foundation**

Run:

```bash
uv sync --extra dev --extra builder
uv run pytest tests/architecture -q
uv run pytest --version
uv run ruff --version
uv run python -m build --version
uv run python -c "import pydantic, httpx"
uv run ruff check .
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .python-version .env.example src tests/architecture
git commit -m "build: initialize full keyword graph package foundation"
```

---

### Task T1: Public Contracts, JSON Schemas, and Examples

**Files:**
- Create: `src/seektalent_keyword_graph/contracts/query_plan.py`
- Create: `src/seektalent_keyword_graph/contracts/snapshot.py`
- Create: `src/seektalent_keyword_graph/contracts/__init__.py`
- Modify: `src/seektalent_keyword_graph/__init__.py`
- Create: `contracts/query-plan/request.example.json`
- Create: `contracts/query-plan/response.example.json`
- Create: `contracts/query-plan/query-plan-request.schema.json`
- Create: `contracts/query-plan/query-plan-response.schema.json`
- Create: `tests/contract/test_query_plan_contract.py`
- Create: `tests/contract/test_contract_schemas.py`

- [ ] **Step 1: Write contract tests**

Tests must validate:

- request defaults and enum validation;
- nested response models for concept sheet, bundles, queries, rejected surfaces,
  lineage, and warnings;
- all bundle type enum values are accepted;
- JSON examples validate through Pydantic;
- generated JSON schemas match committed schema files byte-for-byte;
- removing required public fields would fail tests.

Run:

```bash
uv run pytest tests/contract/test_query_plan_contract.py tests/contract/test_contract_schemas.py -q
```

Expected: FAIL because models and examples are absent.

- [ ] **Step 2: Implement Pydantic models**

Define typed models for:

- `RequirementTerm`;
- `ConceptSheetRow`;
- `QueryPlanQuery`;
- `QueryBundle`;
- `RejectedSurface`;
- `QueryPlanLineage`;
- `QueryPlanWarning`;
- `QueryPlanRequest`;
- `QueryPlanResponse`;
- `SnapshotManifest`;
- `SnapshotMeta`.

Models must forbid unknown enum values, provide safe defaults only when product
semantics define a default, and include schema version literals.

- [ ] **Step 3: Generate and commit contract examples and schemas**

Add examples covering:

- an anchor query;
- a precision query;
- an alias probe;
- an exploration query;
- a fallback query;
- at least one rejected `company_like` surface.

Generate JSON schema from the committed Pydantic models via a small test helper
or script and commit the generated files.

- [ ] **Step 4: Verify contracts**

Run:

```bash
uv run pytest tests/contract -q
uv run ruff check src tests contracts
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src contracts tests/contract
git commit -m "feat: define full query plan and snapshot contracts"
```

---

### Task T2: SQLite Schema, Migrations, and Stores

**Files:**
- Create: `src/seektalent_keyword_graph/storage/sqlite_schema.py`
- Create: `src/seektalent_keyword_graph/storage/sqlite_migrations.py`
- Create: `src/seektalent_keyword_graph/storage/privacy_scan.py`
- Create: `src/seektalent_keyword_graph/builder/build_store.py`
- Create: `src/seektalent_keyword_graph/runtime/errors.py`
- Create: `src/seektalent_keyword_graph/runtime/snapshot_store.py`
- Create: `tests/snapshot/test_sqlite_schema.py`
- Create: `tests/snapshot/test_snapshot_store_negative.py`
- Create: `tests/builder/test_build_store_schema.py`

- [ ] **Step 1: Write schema/store tests**

Tests must assert:

- build DB migration creates every table and index from the spec;
- migration is idempotent;
- runtime snapshot fixture with all required tables/indexes opens read-only;
- missing required table/index/meta key fails with typed errors;
- unsupported schema version fails;
- non-SQLite and corrupt files fail;
- privacy scanner catches `KEYWORD_GRAPH_CTS_`, `tenant_secret`,
  `candidate_list`, `candidate_id`, `resume_text`, and `.env`;
- opening runtime snapshot does not read CTS env vars.

Run:

```bash
uv run pytest tests/snapshot tests/builder/test_build_store_schema.py -q
```

Expected: FAIL because storage and stores are absent.

- [ ] **Step 2: Implement versioned SQL and migration runner**

Create one authoritative SQL source for build DB schema and runtime snapshot
schema. Include `schema_migrations` and all indexes. Do not create tables in
individual command handlers.

- [ ] **Step 3: Implement build store and snapshot store**

`BuildStore` must provide explicit methods to insert/query JD documents,
sections, mentions, blocked candidates, surfaces, concepts, relations,
co-occurrence edges, probe jobs, observations, and events.

`SQLiteSnapshotStore` must open in read-only mode, validate manifest/checksum
when provided, validate required schema/meta/indexes, and expose query methods
for runtime resolver/selector.

- [ ] **Step 4: Verify storage**

Run:

```bash
uv run pytest tests/snapshot tests/builder/test_build_store_schema.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add sqlite schema migrations and stores"
```

---

### Task T3: JD Import, Sectioning, Extraction, and Report

**Files:**
- Create: `src/seektalent_keyword_graph/builder/import_jds.py`
- Create: `src/seektalent_keyword_graph/builder/sections.py`
- Create: `src/seektalent_keyword_graph/builder/extractors.py`
- Create: `src/seektalent_keyword_graph/builder/extract_surfaces.py`
- Create: `src/seektalent_keyword_graph/observability/build_report.py`
- Create: `tests/fixtures/jds/full_flow_jds.jsonl`
- Create: `tests/builder/test_import_jds.py`
- Create: `tests/builder/test_sections.py`
- Create: `tests/builder/test_extract_surfaces.py`
- Create: `tests/builder/test_extraction_report.py`

- [ ] **Step 1: Write import/extraction tests**

Tests must prove:

- valid JSONL rows import with stable `jd_id`, `content_hash`, language, and
  quality flags;
- duplicate content is deduped and reported;
- malformed rows are rejected into an import error report, not silently skipped;
- section splitter records type, text, offsets, and confidence;
- requirement/preferred strength is inferred from section and local markers;
- extraction persists mentions with JD/section/evidence lineage;
- blocked candidates are persisted for company, department, generic, and policy
  terms;
- extraction report includes counts, top surfaces, blocked reason summary, and
  failed records.

Run:

```bash
uv run pytest tests/builder/test_import_jds.py tests/builder/test_sections.py tests/builder/test_extract_surfaces.py tests/builder/test_extraction_report.py -q
```

Expected: FAIL because builder import/extraction behavior is absent.

- [ ] **Step 2: Implement import and sectioning**

Implement local JSONL import with content hash dedupe, quality flags, explicit
bad-record collection, and build event logging. Implement section splitting for
Chinese and English headings, paragraph fallback, offsets, and strength hints.

- [ ] **Step 3: Implement extraction pipeline**

Implement deterministic extractors:

- seed dictionary for languages/tools/frameworks/methods/certificates;
- mixed Chinese/English technical token patterns;
- conservative version tokens such as `Python 3`, `Vue 3`, `Spring Cloud`;
- blocked classifiers for company-like, department-like, generic soft skills,
  compensation, and location-only terms.

Persist mentions, surfaces, blocked candidates, and extraction report. Surface
creation must use normalized text and update `jd_df`/`jd_tf_total` from evidence,
not from fixed fixture values.

- [ ] **Step 4: Verify extraction**

Run:

```bash
uv run pytest tests/builder/test_import_jds.py tests/builder/test_sections.py tests/builder/test_extract_surfaces.py tests/builder/test_extraction_report.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: import jds and extract keyword evidence"
```

---

### Task T4: Surface Normalization, Classification, Concepts, and Alias Evidence

**Files:**
- Create: `src/seektalent_keyword_graph/domain/models.py`
- Create: `src/seektalent_keyword_graph/domain/normalization.py`
- Create: `src/seektalent_keyword_graph/domain/classification.py`
- Create: `src/seektalent_keyword_graph/builder/build_relations.py`
- Create: `tests/unit/test_normalization.py`
- Create: `tests/unit/test_surface_classification.py`
- Create: `tests/builder/test_build_relations.py`
- Create: `tests/builder/test_concept_clustering.py`

- [ ] **Step 1: Write normalization and graph tests**

Tests must prove:

- full-width and mixed case normalize correctly while preserving display text;
- symbols such as `C++`, `C#`, `.NET`, `Node.js` survive normalization;
- Chinese/English mixed tokens keep searchable form;
- `go` is ambiguous and not auto-promoted over `Golang`;
- company/department/generic classifiers produce rejection reasons;
- `k8s` and `Kubernetes` cluster only when relation evidence is present;
- `Vue` and `React` remain separate concepts;
- version variants such as `Vue 3` relate to `Vue` without replacing it;
- relation rows include confidence, evidence_type, status, and created_by.

Run:

```bash
uv run pytest tests/unit/test_normalization.py tests/unit/test_surface_classification.py tests/builder/test_build_relations.py tests/builder/test_concept_clustering.py -q
```

Expected: FAIL because domain classification and relation builder are absent.

- [ ] **Step 2: Implement normalization/classification**

Implement NFKC normalization, casefolding for Latin text, whitespace collapse,
display text preservation, language classification, token class inference,
specificity score, ambiguity score, and query-safe policy inputs.

- [ ] **Step 3: Implement concept clustering and relation persistence**

Build concepts from surface evidence using deterministic rules:

- exact normalized surface groups;
- seed alias map for known abbreviations/translations;
- version variants as relations;
- conservative non-merge for peer frameworks and weak co-occurrence only;
- stable IDs derived from normalized canonical labels.

Persist concepts, concept_surfaces, and surface_relations in the build DB.

- [ ] **Step 4: Verify graph basics**

Run:

```bash
uv run pytest tests/unit/test_normalization.py tests/unit/test_surface_classification.py tests/builder/test_build_relations.py tests/builder/test_concept_clustering.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: build surfaces concepts and alias evidence"
```

---

### Task T5: Co-occurrence Persistence and Sampling Reports

**Files:**
- Create: `src/seektalent_keyword_graph/builder/cooccurrence.py`
- Create: `src/seektalent_keyword_graph/builder/sampling_report.py`
- Create: `tests/builder/test_cooccurrence.py`
- Create: `tests/builder/test_sampling_report.py`

- [ ] **Step 1: Write co-occurrence and sampling tests**

Tests must prove:

- co-occurrence edges are computed for same JD, same section, and title plus
  requirement windows;
- support, Jaccard, and PMI-like values are deterministic on the fixture corpus;
- blocked surfaces do not create serving co-occurrence edges;
- sampling CSV includes headers, risk reason, evidence count, proposed action,
  and target IDs;
- sampling JSONL is machine-readable and replayable;
- high-risk concept merges are included in sampling output.

Run:

```bash
uv run pytest tests/builder/test_cooccurrence.py tests/builder/test_sampling_report.py -q
```

Expected: FAIL because co-occurrence and sampling behavior is absent.

- [ ] **Step 2: Implement co-occurrence and sampling**

Compute windowed co-occurrence from persisted mentions/surfaces, persist edges,
and generate sampling rows from risk rules: ambiguous text, high-frequency new
surface, weak alias, company-like blocker, and concept merge risk.

- [ ] **Step 3: Verify reports**

Run:

```bash
uv run pytest tests/builder/test_cooccurrence.py tests/builder/test_sampling_report.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "feat: persist cooccurrence and sampling reports"
```

---

### Task T6: Fake CTS and Mocked Real CTS Client

**Files:**
- Create: `src/seektalent_keyword_graph/cts/config.py`
- Create: `src/seektalent_keyword_graph/cts/fake_client.py`
- Create: `src/seektalent_keyword_graph/cts/count_client.py`
- Create: `src/seektalent_keyword_graph/cts/retry.py`
- Create: `tests/fixtures/cts/fake_totals.json`
- Create: `tests/cts/test_fake_client.py`
- Create: `tests/cts/test_count_client.py`
- Create: `tests/cts/test_retry.py`

- [ ] **Step 1: Write CTS client tests**

Tests must cover:

- fake success, zero, timeout, 429, 5xx, auth error, network error;
- fake request recording;
- real client mocked HTTP payload uses `page=1` and `pageSize=1`;
- response parser reads only `data.total`;
- candidate items in response are ignored and never returned;
- timeout/429/5xx/auth/invalid/network classifications;
- retry policy retries only retryable errors;
- repr/log-safe rendering redacts tenant secret;
- no test performs real network I/O.

Run:

```bash
uv run pytest tests/cts/test_fake_client.py tests/cts/test_count_client.py tests/cts/test_retry.py -q
```

Expected: FAIL because CTS modules are absent.

- [ ] **Step 2: Implement fake and mocked real clients**

Implement fake response loading from JSON, request recording, and error
simulation. Implement httpx real client with injected transport/client for tests,
explicit timeout, trace id header, status classification, and secret redaction.

- [ ] **Step 3: Verify CTS clients**

Run:

```bash
uv run pytest tests/cts/test_fake_client.py tests/cts/test_count_client.py tests/cts/test_retry.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "feat: add safe cts count clients"
```

---

### Task T7: Probe Jobs, Rate Limit, Window, TTL, Retry, and Dry-run Observations

**Files:**
- Create: `src/seektalent_keyword_graph/cts/rate_limit.py`
- Create: `src/seektalent_keyword_graph/cts/probe_window.py`
- Create: `src/seektalent_keyword_graph/builder/cts_probe.py`
- Create: `tests/cts/test_rate_limit.py`
- Create: `tests/cts/test_probe_window.py`
- Create: `tests/builder/test_cts_probe_runner.py`

- [ ] **Step 1: Write probe runner tests**

Tests must prove:

- default config is 1 RPS, concurrency 1, 09:00-21:00 Asia/Shanghai;
- outside window real probe is blocked but dry-run is allowed;
- explicit real mode without `--gate-file` fails closed;
- real mode with a gate file whose first line is not
  `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH` fails closed;
- real mode with valid gate file, credentials, and window can execute only
  against mocked HTTP in tests;
- TTL dedupe skips fresh observations with same query hash/mode;
- timeout/429/5xx/network produce retry jobs with backoff;
- auth error pauses pending jobs and does not retry;
- failure observations do not overwrite old successful totals;
- fake/dry-run persists observations and probe job status in build DB;
- concurrency never exceeds configured limit under an async test.

Run:

```bash
uv run pytest tests/cts/test_rate_limit.py tests/cts/test_probe_window.py tests/builder/test_cts_probe_runner.py -q
```

Expected: FAIL because probe runner/rate limit behavior is absent.

- [ ] **Step 2: Implement gate, rate limit, and runner**

Implement timezone-aware window checks, explicit gate-file parsing, local async
token bucket, semaphore concurrency gate, TTL dedupe, retry/backoff scheduling,
job leasing, fake observation persistence, and event logging. The gate-file
parser must accept only a file whose first line is exactly
`REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`.

- [ ] **Step 3: Verify probe runner**

Run:

```bash
uv run pytest tests/cts/test_rate_limit.py tests/cts/test_probe_window.py tests/builder/test_cts_probe_runner.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "feat: add gated cts probe runner"
```

---

### Task T8: Snapshot Build, Manifest, Checksum, and Validation

**Files:**
- Create: `src/seektalent_keyword_graph/builder/build_snapshot.py`
- Create: `src/seektalent_keyword_graph/builder/validate_snapshot.py`
- Create: `src/seektalent_keyword_graph/release_validation.py`
- Create: `tests/builder/test_build_snapshot.py`
- Create: `tests/snapshot/test_validate_snapshot.py`
- Create: `tests/unit/test_release_validation.py`

- [ ] **Step 1: Write snapshot build/validation tests**

Tests must prove:

- build snapshot projects concepts, surfaces, relations, co-occurrence, and latest
  valid CTS observations from build DB;
- all required runtime tables/indexes/meta keys exist;
- manifest and checksum are written and match snapshot bytes;
- compressed snapshot is produced;
- privacy markers are rejected;
- candidate/resume/CTS secret markers are rejected;
- referential integrity failures are rejected;
- serving surface without valid/stale/unknown policy observation is rejected;
- changed snapshot bytes fail manifest validation;
- oversized compressed artifact fails validation.

Run:

```bash
uv run pytest tests/builder/test_build_snapshot.py tests/snapshot/test_validate_snapshot.py tests/unit/test_release_validation.py -q
```

Expected: FAIL because snapshot build and validation are absent.

- [ ] **Step 2: Implement snapshot build and validation**

Project build DB rows into runtime schema with deterministic ordering, latest
valid observation selection, recall bucket calculation, build report hash,
manifest sha256, gzip compression, privacy scan, referential checks, and release
validation result object.

- [ ] **Step 3: Verify snapshot artifacts**

Run:

```bash
uv run pytest tests/builder/test_build_snapshot.py tests/snapshot/test_validate_snapshot.py tests/unit/test_release_validation.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "feat: build and validate runtime snapshots"
```

---

### Task T9: Runtime Resolver, Selector, Bundle Builder, and Query Planner

**Files:**
- Create: `src/seektalent_keyword_graph/domain/scoring.py`
- Create: `src/seektalent_keyword_graph/domain/policies.py`
- Create: `src/seektalent_keyword_graph/runtime/concept_resolver.py`
- Create: `src/seektalent_keyword_graph/runtime/surface_selector.py`
- Create: `src/seektalent_keyword_graph/runtime/bundle_builder.py`
- Create: `src/seektalent_keyword_graph/runtime/query_planner.py`
- Modify: `src/seektalent_keyword_graph/engine.py`
- Create: `tests/runtime/test_concept_resolver.py`
- Create: `tests/runtime/test_surface_selector.py`
- Create: `tests/runtime/test_bundle_builder.py`
- Create: `tests/runtime/test_query_planner.py`

- [ ] **Step 1: Write runtime behavior tests**

Tests must prove:

- same input and snapshot produce identical response ordering;
- concept resolution uses requirement terms, title, JD text, and notes;
- company/department/generic terms are rejected with reason;
- healthy required surfaces become anchor queries;
- too-wide surfaces require companion and become precision;
- zero/too-narrow/stale surfaces with aliases become alias_probe;
- safe unknown extracted terms become exploration;
- fallback appears only when no graph-backed route is trustworthy;
- warnings include no match, stale observation, unknown observation, and fallback;
- lineage includes input hash, snapshot schema, policy version, and source refs;
- `max_query_bundles` is respected;
- no runtime path imports builder/CTS or reads CTS env.

Run:

```bash
uv run pytest tests/runtime/test_concept_resolver.py tests/runtime/test_surface_selector.py tests/runtime/test_bundle_builder.py tests/runtime/test_query_planner.py -q
```

Expected: FAIL because runtime planner behavior is absent.

- [ ] **Step 2: Implement scoring and policies**

Implement recall bucket thresholds as policy data, freshness score, specificity
and ambiguity weighting, requirement strength weighting, rejection reason
calculation, and deterministic sorting keys.

- [ ] **Step 3: Implement resolver, selector, bundle builder, planner**

Use `SQLiteSnapshotStore` query methods. Do not access builder DB. Build response
models from runtime rows and domain decisions only.

- [ ] **Step 4: Verify runtime planning**

Run:

```bash
uv run pytest tests/runtime/test_concept_resolver.py tests/runtime/test_surface_selector.py tests/runtime/test_bundle_builder.py tests/runtime/test_query_planner.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: plan recall-aware query bundles"
```

---

### Task T10: Real Local CLI Command Flows

**Files:**
- Modify: `src/seektalent_keyword_graph/cli.py`
- Create: `tests/cli/test_cli_commands.py`
- Create: `tests/integration/test_cli_end_to_end.py`

- [ ] **Step 1: Write CLI tests**

Tests must prove:

- all promised commands have help output;
- `import-jds` creates a build DB from fixture JSONL;
- `extract-surfaces` updates the build DB and writes extraction report;
- `build-relations` updates concept/relation/co-occurrence tables and writes
  sampling CSV/JSONL;
- `probe-cts --dry-run --fake-response` writes fake observations and no real CTS
  call occurs;
- `build-snapshot` writes snapshot, manifest, compressed artifact, and build
  report;
- `validate-snapshot` exits 0 for valid artifacts and non-zero for invalid ones;
- invalid arguments return non-zero and actionable stderr;
- `probe-cts --real` fails closed without a valid gate file.
- `probe-cts --real --gate-file bad.txt` fails closed when the gate content is
  not exactly `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`.

Run:

```bash
uv run pytest tests/cli/test_cli_commands.py tests/integration/test_cli_end_to_end.py -q
```

Expected: FAIL because CLI does not execute full local flow.

- [ ] **Step 2: Implement CLI dispatch**

Implement `argparse` subcommands with typed arguments and handlers that call the
builder/release APIs. Command handlers must return process exit codes and print
machine-readable JSON reports for non-trivial commands.

- [ ] **Step 3: Verify CLI**

Run:

```bash
uv run pytest tests/cli/test_cli_commands.py tests/integration/test_cli_end_to_end.py -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "feat: wire real local keyword graph cli flows"
```

---

### Task T11: Replay Evaluation and Full JD-to-Runtime Integration

**Files:**
- Create: `src/seektalent_keyword_graph/observability/replay_report.py`
- Create: `scripts/run_fixture_flow.py`
- Create: `tests/fixtures/eval_jds/*.jsonl`
- Create: `tests/integration/test_jd_to_query_plan.py`
- Create: `tests/integration/test_replay_report.py`

- [ ] **Step 1: Write integration/replay tests**

Tests must prove the full fixture flow:

```text
JD JSONL -> build DB -> sections -> mentions -> concepts/relations/cooccurrence
-> fake CTS observations -> runtime snapshot + manifest -> KeywordGraph.open
-> build_query_plan
```

The fixture set must include cases that produce each bundle type and at least one
blocked company/department term. Replay report tests must assert case count,
bundle type counts, warning counts, rejected reason counts, and deterministic
stability across two runs.

Run:

```bash
uv run pytest tests/integration/test_jd_to_query_plan.py tests/integration/test_replay_report.py -q
```

Expected: FAIL until the full local flow and report are wired.

- [ ] **Step 2: Implement fixture flow and replay report**

Create reusable fixture flow script using package APIs, not shell-only glue.
Replay report must serialize JSON with summary metrics and per-case lineage.

- [ ] **Step 3: Verify integration**

Run:

```bash
uv run pytest tests/integration/test_jd_to_query_plan.py tests/integration/test_replay_report.py -q
uv run python scripts/run_fixture_flow.py --work-dir /tmp/kg-fixture-flow
uv run ruff check src tests scripts
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add src scripts tests
git commit -m "test: add jd to query plan integration flow"
```

---

### Task T12: SeekTalent Consumer Contracts and Docs

**Files:**
- Create: `docs/seektalent-integration.md`
- Create: `docs/query-plan-contract.md`
- Create: `tests/contract/test_consumer_contract.py`
- Modify: `contracts/query-plan/request.example.json`
- Modify: `contracts/query-plan/response.example.json`

- [ ] **Step 1: Write consumer contract tests**

Tests must prove:

- `SEEKTALENT_KEYWORD_GRAPH_*` config model loads runtime settings only;
- no `KEYWORD_GRAPH_CTS_*` env is read by runtime config;
- a sample consumer can call `KeywordGraph.open` and `build_query_plan`;
- missing package/snapshot is represented as `keyword_graph_unavailable` in the
  documented fail-open adapter example;
- request/response examples include real bundles and lineage from the fixture
  snapshot;
- no SeekTalent module import exists.

Run:

```bash
uv run pytest tests/contract/test_consumer_contract.py -q
```

Expected: FAIL because consumer docs/examples/config behavior are absent.

- [ ] **Step 2: Implement docs and examples**

Document env vars, failure mode, artifacts, no-CTS-user boundary, package import
example, fail-open adapter pseudocode, and contract compatibility rules. Update
examples from fixture flow output.

- [ ] **Step 3: Verify consumer contract**

Run:

```bash
uv run pytest tests/contract -q
uv run ruff check src tests
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add docs contracts tests
git commit -m "docs: add seektalent consumer contract"
```

---

### Task T13: Release Hardening, Import Boundaries, and Wheel Smoke

**Files:**
- Create: `docs/release-checklist.md`
- Create: `docs/runbooks/rollback-snapshot.md`
- Create: `scripts/write_readiness_report.py`
- Create: `tests/architecture/test_import_boundaries.py`
- Create: `tests/architecture/test_no_seektalent_import.py`
- Create: `tests/architecture/test_runtime_no_cts_env.py`
- Create: `tests/integration/test_wheel_smoke.py`
- Create: `tests/integration/test_snapshot_artifact_validation.py`

- [ ] **Step 1: Write release/architecture tests**

Tests must prove:

- runtime modules do not import builder/CTS;
- domain modules do not import runtime/builder/CTS;
- package modules do not import SeekTalent;
- package import does not read CTS env;
- wheel builds and installs into a temp venv;
- installed wheel can import package and open a fixture snapshot;
- artifact validation rejects secrets, candidate markers, resume markers,
  checksum mismatch, missing manifest, and oversized compressed artifact;
- rollback docs and release checklist contain required commands and gates.

Run:

```bash
uv run pytest tests/architecture tests/integration/test_wheel_smoke.py tests/integration/test_snapshot_artifact_validation.py -q
```

Expected: FAIL until hardening artifacts/tests are implemented.

- [ ] **Step 2: Implement hardening docs/scripts/tests**

Implement release validation helpers if not already covered, rollback runbook,
release checklist, wheel smoke helper, and architecture import scanners.

- [ ] **Step 3: Verify release hardening**

Run:

```bash
uv run pytest tests/architecture tests/integration/test_wheel_smoke.py tests/integration/test_snapshot_artifact_validation.py -q
uv run python -m build --wheel
uv run ruff check .
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add docs scripts tests src
git commit -m "chore: harden release and architecture gates"
```

---

### Task T14: Readiness Report and Final Verification

**Files:**
- Modify: `scripts/write_readiness_report.py`
- Create/Update: `docs/readiness-report.md`

- [ ] **Step 1: Write readiness report tests**

Tests must prove:

- report generation runs the exact final commands;
- report contains current HEAD;
- report maps every M0-M7 acceptance item to a test or command;
- report includes explicit incomplete items section, even when empty;
- report does not contain blank statuses;
- report records old-name scan exit 1 as success/no matches.

Run:

```bash
uv run pytest tests/integration/test_readiness_report.py -q
```

Expected: FAIL until report writer covers all required evidence.

- [ ] **Step 2: Implement readiness report writer**

The writer must run:

```bash
uv sync --extra dev --extra builder
uv run pytest
uv run ruff check .
uv run python -m build --wheel
uv run pytest tests/architecture/test_import_boundaries.py -q
rg -n "seektalent-keyword-intel|seektalent_keyword_intel|KEYWORD_INTEL|keyword_intelligence" \
  README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts docs
uv run pytest tests/integration/test_cli_end_to_end.py -q
uv run pytest tests/integration/test_jd_to_query_plan.py -q
```

It must also run the fixture snapshot build + manifest + checksum + validation
flow and include each command's exit code and first meaningful output line.

- [ ] **Step 3: Generate final report**

Run:

```bash
uv run python scripts/write_readiness_report.py
rg -n "status:$|pytest:$|ruff check \\.:$|Commit:$" docs/readiness-report.md
```

Expected:

- report writer exits 0;
- blank-status scan exits 1 with no matches;
- report includes current `git rev-parse HEAD`.

- [ ] **Step 4: Final fresh verification**

Run:

```bash
uv sync --extra dev --extra builder
uv run pytest
uv run ruff check .
uv run python -m build --wheel
uv run pytest tests/architecture/test_import_boundaries.py -q
rg -n "seektalent-keyword-intel|seektalent_keyword_intel|KEYWORD_INTEL|keyword_intelligence" \
  README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts docs
uv run pytest tests/integration/test_cli_end_to_end.py -q
uv run pytest tests/integration/test_jd_to_query_plan.py -q
```

Expected:

- all commands except old-name scan exit 0;
- old-name scan exits 1 with no matches.

- [ ] **Step 5: Commit**

```bash
git add scripts/write_readiness_report.py docs/readiness-report.md tests/integration/test_readiness_report.py
git commit -m "docs: report full keyword graph readiness"
```

---

## Self-Review

### Spec Coverage

- M0 is covered by T0 and T13/T14 wheel/import verification.
- M1 is covered by T1, T2, and T9 runtime behavior.
- M2 is covered by T3 and T10 CLI execution.
- M3 is covered by T4 and T5.
- M4 is covered by T6 and T7.
- M5 is covered by T8, T9, T10, and T11.
- M6 is covered by T12.
- M7 is covered by T13 and T14.

### Anti-Shortcut Coverage

- T0 adds production-source shortcut guards.
- Every task starts with acceptance tests that fail before implementation.
- CLI tests require local data mutation and artifact output, not help text.
- Integration tests require JD fixture -> build DB -> snapshot -> runtime query.
- Readiness report must list incomplete items explicitly.

### Type and Naming Consistency

- Distribution: `seektalent-keyword-graph`.
- Import package: `seektalent_keyword_graph`.
- Runtime class: `KeywordGraph`.
- CLI command: `keyword-graph`.
- Runtime env prefix: `SEEKTALENT_KEYWORD_GRAPH_`.
- Builder CTS env prefix: `KEYWORD_GRAPH_CTS_`.
- Snapshot schema: `snapshot-v1`.
- Selection policy: `policy-v1`.

### Review Gate

This plan is ready for `fw-plan-review`. No UI/UX work is in scope, so
`plan-design-review` should be skipped unless the reviewer identifies a hidden
user-facing surface beyond CLI/docs/contracts.

## GSTACK PLAN REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| Eng Review | `fw-plan-review` | Architecture, code quality, tests, performance | 1 | CLEARED | 1 P1 gate-specific issue found and addressed inline; no remaining P1/P2 blockers |
| Design Review | `fw-plan-review` | UI/UX gaps | 0 | SKIPPED | No UI, visual workflow, or user-facing screen scope |

### Step 0 Scope Challenge

This plan intentionally touches far more than 8 files and introduces multiple
modules because the requested deliverable is a new package, internal builder,
snapshot artifact pipeline, runtime selector, CLI, contracts, and release
validation. Reducing the scope to fewer modules would recreate the rejected
2026-05-30 MVP shape and would fail the user's explicit requirement for a
complete first version.

Existing code does not partially solve the implementation because the previous
generated source tree was removed. The remaining repository content is planning
documentation only. Reusing SeekTalent main-project code is out of scope because
the package must not import SeekTalent or modify the SeekTalent project.

Scope accepted as-is with two controls:

- every task is gated by acceptance tests before implementation;
- execution will use sequential subagent-driven tasks with spec and quality
  review after each task.

### Architecture Review

`[P1] (confidence: 9/10) docs/superpowers/specs/2026-05-31-keyword-graph-full-m0-m7.md:303` — The initial plan said real CTS required an explicit gate, but did not define a concrete, testable gate mechanism. That left room for ambiguous implementation and could allow a worker to invent a permissive flag.

Resolution applied:

- real CTS now requires `--real`, `--gate-file PATH`, exact first-line content
  `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`, valid credentials, and configured time
  window;
- gated success can be tested only with mocked HTTP;
- CLI and probe-runner tests must cover missing, invalid, and valid mocked gate
  paths.

No remaining architecture blockers found. The dependency graph preserves the
runtime/builder/CTS split:

```text
contracts -> domain
runtime   -> contracts + domain + storage
engine    -> runtime + contracts
builder   -> contracts + domain + storage + cts
cli       -> builder + release validation
cts       -> httpx + fake/mocked probe behavior
```

### Code Quality Review

No P1/P2 code-organization blockers found in the plan. The file map is larger
than a small feature, but it is split by responsibility:

- contracts own public API shape;
- domain owns pure rules;
- storage owns SQLite schema/migrations/scans;
- runtime owns read-only planning;
- builder owns stateful construction;
- CTS owns builder-only count probing;
- release/observability own artifact evidence.

Potential lower-severity risk to watch during `fw-build`: avoid turning
`BuildStore` or `SQLiteSnapshotStore` into broad god objects. If either grows
too large during implementation, split query groups by responsibility while
keeping the public store API stable.

### Test Review

The plan includes acceptance-level tests for each meaningful code path before
implementation. Coverage target is complete behavior coverage rather than smoke
tests.

```text
CODE PATHS
[+] Package foundation
  ├── [PLANNED] uv sync/tool smoke
  ├── [PLANNED] source import
  ├── [PLANNED] wheel build/install smoke
  └── [PLANNED] anti-shortcut/import-boundary scanners
[+] Contracts
  ├── [PLANNED] request defaults and enum validation
  ├── [PLANNED] nested response models for all bundle types
  ├── [PLANNED] examples validate through models
  └── [PLANNED] generated JSON schemas match committed schemas
[+] Build DB and import
  ├── [PLANNED] migrations idempotent
  ├── [PLANNED] JD import dedupe and bad-record report
  ├── [PLANNED] section offsets and requirement strength
  └── [PLANNED] extraction report with blocked reasons
[+] Graph builder
  ├── [PLANNED] normalization and classification edge cases
  ├── [PLANNED] k8s/Kubernetes evidence-based merge
  ├── [PLANNED] Vue/React non-merge
  ├── [PLANNED] relation evidence persistence
  └── [PLANNED] co-occurrence + sampling CSV/JSONL
[+] CTS builder-only flow
  ├── [PLANNED] fake success/zero/timeout/429/5xx/auth/network
  ├── [PLANNED] mocked real HTTP payload and parsing
  ├── [PLANNED] RPS/concurrency/window/TTL/retry/auth pause
  └── [PLANNED] real CTS gate failure without valid gate file
[+] Snapshot and runtime
  ├── [PLANNED] snapshot build from build DB
  ├── [PLANNED] manifest/checksum/compression/privacy validation
  ├── [PLANNED] negative snapshot cases
  ├── [PLANNED] anchor/precision/alias_probe/exploration/fallback
  └── [PLANNED] deterministic JD-to-query-plan integration
[+] CLI and release
  ├── [PLANNED] every CLI command mutates local DB or writes artifacts
  ├── [PLANNED] validate-snapshot success/failure
  ├── [PLANNED] old-name scan
  └── [PLANNED] readiness report maps M0-M7 to evidence

COVERAGE: 38/38 planned code-path groups covered by tests
QUALITY: smoke-only assertions are explicitly rejected by T0/T14 gates
```

No remaining test blockers found. The key future review point is to ensure
subagents write behavior tests matching these requirements rather than only
checking function existence.

### Performance Review

No P1/P2 performance blockers found. The plan uses boring local technology:

- SQLite build DB for internal state;
- SQLite read-only snapshot for runtime;
- indexed lookup and bounded relation expansion;
- no service process, queue, Redis, graph DB, or Docker runtime;
- conservative CTS probe defaults of 1 RPS and concurrency 1.

Performance risks are covered by planned indexes, deterministic query limits,
and release validation on compressed snapshot size. During build, add targeted
tests for `EXPLAIN QUERY PLAN` only if fixture queries show accidental table
scans on hot runtime paths.

### Verdict

PLAN REVIEW CLEARED for implementation planning purposes.

Per repository stage gates, stop before `fw-build`. The next stage should use
`fw-build` with `superpowers:subagent-driven-development` as selected above.
