# Readiness Report

Verified implementation HEAD: `fcf1ed4fa215a0ec8d4e3a18bc849bff95b6e47e`
Note: A later report-refresh commit may store this generated report; the verified implementation HEAD above is the code revision checked.
Overall status: complete

## Verification Commands

- `uv sync --extra dev --extra builder`
- `uv run pytest`
- `uv run ruff check .`
- `uv run python -m build --wheel`
- `uv run pytest tests/architecture/test_import_boundaries.py -q`
- `rg -n "<legacy-name denylist pattern from scripts/write_readiness_report.py>" README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts docs`
- `uv run pytest tests/integration/test_cli_end_to_end.py -q`
- `uv run pytest tests/integration/test_jd_to_query_plan.py -q`
- `uv run pytest tests/integration/test_query_recall_optimization.py -q`
- `uv run python scripts/run_fixture_flow.py --work-dir '/private/tmp/readiness fixture ; safe'`
- `uv run keyword-graph validate-snapshot --snapshot '/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3' --manifest '/private/tmp/readiness fixture ; safe/snapshot/snapshot-manifest.json' --compressed-snapshot '/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3.gz'`

## Final Verification Evidence

- Command: `uv sync --extra dev --extra builder`
  Exit code: 0
  Status: success
  First meaningful output line: Resolved 24 packages in 4ms
- Command: `uv run pytest`
  Exit code: 0
  Status: success
  First meaningful output line: ============================= test session starts ==============================
- Command: `uv run ruff check .`
  Exit code: 0
  Status: success
  First meaningful output line: All checks passed!
- Command: `uv run python -m build --wheel`
  Exit code: 0
  Status: success
  First meaningful output line: Successfully built seektalent_keyword_graph-0.1.0-py3-none-any.whl
- Command: `uv run pytest tests/architecture/test_import_boundaries.py -q`
  Exit code: 0
  Status: success
  First meaningful output line: ........                                                                 [100%]
- Command: `rg -n "<legacy-name denylist pattern from scripts/write_readiness_report.py>" README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts docs`
  Exit code: 1
  Status: success/no matches
  First meaningful output line: (no output)
- Command: `uv run pytest tests/integration/test_cli_end_to_end.py -q`
  Exit code: 0
  Status: success
  First meaningful output line: ....                                                                     [100%]
- Command: `uv run pytest tests/integration/test_jd_to_query_plan.py -q`
  Exit code: 0
  Status: success
  First meaningful output line: .                                                                        [100%]
- Command: `uv run pytest tests/integration/test_query_recall_optimization.py -q`
  Exit code: 0
  Status: success
  First meaningful output line: ..                                                                       [100%]
- Command: `uv run python scripts/run_fixture_flow.py --work-dir '/private/tmp/readiness fixture ; safe'`
  Exit code: 0
  Status: success
  First meaningful output line: "build_db_path": "/private/tmp/readiness fixture ; safe/build.sqlite3",
- Command: `uv run keyword-graph validate-snapshot --snapshot '/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3' --manifest '/private/tmp/readiness fixture ; safe/snapshot/snapshot-manifest.json' --compressed-snapshot '/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3.gz'`
  Exit code: 0
  Status: success
  First meaningful output line: {"command": "validate-snapshot", "compressed_snapshot": "/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3.gz", "errors": [], "gzip_sha256": "dcddc9f4598281c2bd6de5eabe50427799b902c147edd43b22e006163ed58a6c", "manifest": "/private/tmp/readiness fixture ; safe/snapshot/snapshot-manifest.json", "ok": true, "snapshot": "/private/tmp/readiness fixture ; safe/snapshot/keyword-graph.sqlite3", "snapshot_sha256": "a948b3af812fad7fcca53a0ed9bd15a8227ee105ac638d5622407cb1dfb49918", "status": "ok"}

## Query Recall Optimization Status

Completion status: complete
Evidence: `uv run pytest tests/integration/test_query_recall_optimization.py -q`; fixture flow query recall responses; provider-aware snapshot validation.

## Provider-Aware Snapshot Status

Completion status: complete
Evidence: fixture snapshot build, manifest, checksum, gzip artifact, `provider_recall_observations`, and `keyword-graph validate-snapshot`.

## Acceptance Evidence Matrix

### M0

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| `uv sync --extra dev --extra builder` succeeds. | `uv sync --extra dev --extra builder` | complete |
| `uv run pytest --version`, `uv run ruff --version`, and `uv run python -m build --version` succeed. | `uv run pytest`, `uv run ruff check .`, and `uv run python -m build --wheel` | complete |
| `uv run python -c "import pydantic, httpx"` succeeds. | `uv sync --extra dev --extra builder` | complete |
| Package metadata name is `seektalent-keyword-graph`. | `uv run python -m build --wheel` | complete |
| Package import succeeds from source and from built wheel. | `uv run pytest` and `uv run python -m build --wheel` | complete |
| No CTS client is reachable from runtime import paths. | `uv run pytest tests/architecture/test_import_boundaries.py -q` | complete |
| No real CTS call exists in tests or default CLI behavior. | `uv run pytest` | complete |

### M1

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Typed Pydantic contracts validate examples and generate JSON schemas. | `uv run pytest` | complete |
| Read-only snapshot open succeeds for a valid fixture. | Fixture flow and validation command | complete |
| Manifest checksum validation succeeds and fails on mismatch. | `uv run pytest` and fixture validation command | complete |
| Missing, unsupported, corrupt, incomplete, or privacy-violating snapshots raise typed errors. | `uv run pytest` | complete |
| Lookup APIs return concepts, surfaces, relations, recall summaries, and alternatives from snapshot data. | `uv run pytest tests/integration/test_jd_to_query_plan.py -q` | complete |
| Query Recall Optimization contracts validate provider-aware examples and generated JSON schemas. | `uv run pytest tests/integration/test_query_recall_optimization.py -q` | complete |
| Runtime import and environment tests prove no builder/CTS import and no CTS env read. | `uv run pytest tests/architecture/test_import_boundaries.py -q` | complete |

### M2

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Fixture JSONL imports into build DB with dedupe and bad-record report. | `uv run pytest` and fixture flow command | complete |
| JD sections persist with offsets and section type. | `uv run pytest` and fixture flow command | complete |
| Mentions persist with JD/section/evidence lineage and requirement strength. | `uv run pytest` and fixture flow command | complete |
| Company-like, department-like, generic, and blocked policy terms are persisted as blocked candidates, not serving surfaces. | `uv run pytest` | complete |
| Extraction report includes counts, top surfaces, blocked reason summary, and failed records. | `uv run pytest` and fixture flow command | complete |
| `keyword-graph import-jds` and `keyword-graph extract-surfaces` run against local fixtures and write expected DB/report artifacts. | `uv run pytest tests/integration/test_cli_end_to_end.py -q` | complete |

### M3

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Surface normalization, language classification, token class, specificity, and ambiguity are persisted. | `uv run pytest` | complete |
| Concept clustering creates stable concept IDs from normalized evidence. | `uv run pytest` | complete |
| Alias evidence merges `k8s` and `Kubernetes`; weak evidence does not merge `Vue` and `React`. | `uv run pytest` | complete |
| Relations persist with confidence, evidence type, status, and created_by. | `uv run pytest` | complete |
| Co-occurrence edges persist with support, Jaccard, and PMI-like values. | `uv run pytest` | complete |
| Sampling CSV and JSONL are generated with risk reasons and review targets. | `uv run pytest` | complete |
| `keyword-graph build-relations` runs against a fixture build DB and writes relation/co-occurrence/sampling outputs. | `uv run pytest tests/integration/test_cli_end_to_end.py -q` | complete |

### M4

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Fake CTS covers success, zero, timeout, 429, 5xx, auth, and network error. | `uv run pytest` | complete |
| Real CTS client has complete mocked HTTP tests and never calls the network in CI. | `uv run pytest` | complete |
| Probe runner enforces RPS, concurrency, time window, TTL dedupe, retry/backoff, and auth pause. | `uv run pytest` | complete |
| `probe-cts --dry-run` writes planned jobs/payloads or fake observations without touching real CTS. | `uv run pytest tests/integration/test_cli_end_to_end.py -q` | complete |
| `probe-cts --real` fails closed unless `--gate-file` exists, contains `REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`, credentials are present, and the current time is inside the configured window; gated success is covered only with mocked HTTP. | `uv run pytest` | complete |
| Runtime package does not import CTS code and does not read CTS env. | `uv run pytest tests/architecture/test_import_boundaries.py -q` | complete |
| Probe persistence writes provider-aware rows with `provider='cts'`; runtime does not depend on a CTS-only recall table. | `uv run pytest tests/integration/test_query_recall_optimization.py -q` | complete |

### M5

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Snapshot builder projects build DB contents into all required runtime tables and indexes, including `provider_recall_observations`. | Fixture flow and validation command | complete |
| Snapshot manifest/checksum/build report are generated. | Fixture flow and validation command | complete |
| Snapshot validation rejects schema, referential, privacy, checksum, and size failures. | `uv run pytest` and validation command | complete |
| Runtime query planner emits real anchor, precision, alias_probe, exploration, and fallback bundles when fixture evidence calls for each type. | `uv run pytest tests/integration/test_jd_to_query_plan.py -q` | complete |
| Runtime `analyze_query_recall` and `optimize_query_terms` emit provider-aware input observations, graph alternatives, relation provenance, recall warnings, and term-pool actions for fixture evidence. | `uv run pytest tests/integration/test_query_recall_optimization.py -q` | complete |
| Runtime query recall behavior distinguishes unsupported provider, no match, matched-without-observation, zero recall, too-wide recall, stale observation, unknown observation, and multiple provider rows. | `uv run pytest tests/integration/test_query_recall_optimization.py -q` | complete |
| Response includes concept sheet, reason codes, rejected surfaces, warnings, and lineage with input hash and policy version. | `uv run pytest tests/integration/test_jd_to_query_plan.py -q` | complete |
| Replay evaluation report is generated and includes bundle counts, warning counts, rejected reason counts, query recall action counts, provider observation status counts, and stability checks. | `uv run pytest` and fixture flow command | complete |
| Integration flow from JD fixture to runtime response passes. | `uv run pytest tests/integration/test_jd_to_query_plan.py -q` | complete |

### M6

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Contract examples and JSON schemas are stable and validated. | `uv run pytest` | complete |
| Consumer tests demonstrate how SeekTalent would load config, call the package, and fail open with `keyword_graph_unavailable`. | `uv run pytest` | complete |
| Docs define `SEEKTALENT_KEYWORD_GRAPH_*` env vars and no-CTS-user boundary. | `uv run pytest` | complete |
| Docs show where Query Recall Optimization fits between SeekTalent query term pool generation and provider retrieval, with example request/response for `optimize_query_terms`. | `uv run pytest` | complete |
| No SeekTalent main-project files are modified. | `git status --short` before commit and this scoped T16 commit | complete |

### M7

| Acceptance item | Evidence | Status |
| --- | --- | --- |
| Wheel builds and wheel install smoke passes. | `uv run python -m build --wheel` and `uv run pytest` | complete |
| Artifact validation checks compressed size, manifest, checksum, secret markers, candidate markers, resume markers, and old names. | Validation command and old-name scan | complete |
| CLI fixture flow runs end-to-end. | `uv run pytest tests/integration/test_cli_end_to_end.py -q` | complete |
| Import-boundary tests cover runtime, domain, builder, CTS, and SeekTalent. | `uv run pytest tests/architecture/test_import_boundaries.py -q` | complete |
| Release checklist, rollback instructions, and readiness report exist. | `uv run pytest` and generated `docs/readiness-report.md` | complete |
| `docs/readiness-report.md` maps every M0-M7 acceptance item to fresh test or command evidence, separately lists Query Recall Optimization status, lists incomplete items explicitly, and includes the verified implementation HEAD. | `uv run pytest tests/integration/test_readiness_report.py -q` | complete |

## Incomplete Items

- None.
