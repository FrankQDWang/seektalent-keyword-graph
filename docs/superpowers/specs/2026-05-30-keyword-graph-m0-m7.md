# Keyword Graph M0-M7 Spec

## Purpose

Build `seektalent-keyword-graph` from the current planning repository into an independent, lightweight Python package and snapshot builder that SeekTalent can consume as a dependency.

Dependency direction is fixed:

```text
SeekTalent -> seektalent-keyword-graph package + SQLite snapshot
```

`seektalent-keyword-graph` must not import SeekTalent.

## Product Boundary

First version does:

- Build a keyword-only concept / surface graph from public JD samples and local fixtures.
- Provide a local Python runtime package.
- Read a readonly SQLite snapshot.
- Return deterministic `QueryPlanResponse` objects with query bundles, rejected surfaces, lineage, and warnings.
- Provide internal builder tools for JD import, surface extraction, relation building, fake CTS probing, snapshot building, and snapshot validation.
- Support real CTS count probing only as an internal, explicitly gated builder flow.

First version does not:

- Build a UI.
- Run a local HTTP service.
- Require Docker, Neo4j, PostgreSQL, Redis, Celery, or Kubernetes.
- Require user-side CTS keys.
- Run user-side realtime CTS probing.
- Store resume text, candidate lists, contact details, or candidate-level feedback.
- Build company, industry, department, person, or candidate graphs.

## Naming

- Repository and Python distribution: `seektalent-keyword-graph`
- Python import package: `seektalent_keyword_graph`
- Public runtime class: `KeywordGraph`
- CLI command: `keyword-graph`
- SeekTalent runtime env prefix: `SEEKTALENT_KEYWORD_GRAPH_`
- Internal builder CTS env prefix: `KEYWORD_GRAPH_CTS_`

## Runtime Contract

Runtime API:

```python
from seektalent_keyword_graph import KeywordGraph, QueryPlanRequest

engine = KeywordGraph.open(snapshot_path)
response = engine.build_query_plan(
    QueryPlanRequest(
        request_id="req_001",
        seek_talent_run_id="run_001",
        job_title="Python backend engineer",
        jd_text="...",
        requirement_terms=[
            {"text": "Python", "strength": "required"},
            {"text": "Kubernetes", "strength": "preferred"},
        ],
        max_query_bundles=4,
    )
)
```

Runtime must:

- Open SQLite snapshots read-only.
- Validate snapshot metadata before use.
- Fail clearly when snapshot is missing, incompatible, or corrupt.
- Return fallback warnings instead of blocking SeekTalent when possible.
- Produce deterministic output for the same input and snapshot.
- Never call CTS.
- Never read CTS credentials.

## Snapshot Contract

Runtime snapshot is a SQLite file with at least:

- `snapshot_meta`
- `concepts`
- `surfaces`
- `concept_surfaces`
- `surface_relations`
- `cooccurrence_edges`
- `cts_recall_observations`
- `selection_policy_meta`

Snapshot release requirements:

- Compressed snapshot target `<50MB`.
- Compressed snapshot hard limit `<100MB`.
- Contains no CTS key.
- Contains no CTS candidate list.
- Contains no resume text.
- Contains no raw `.env` values.
- Has manifest and checksum.

## Builder Contract

Builder CLI commands:

```text
keyword-graph import-jds ...
keyword-graph extract-surfaces ...
keyword-graph build-relations ...
keyword-graph probe-cts ...
keyword-graph build-snapshot ...
keyword-graph validate-snapshot ...
```

Builder can use internal credentials only for CTS count probing. Real CTS defaults:

- `KEYWORD_GRAPH_CTS_PROBE_MAX_RPS=1`
- `KEYWORD_GRAPH_CTS_PROBE_MAX_CONCURRENCY=1`
- `KEYWORD_GRAPH_CTS_PROBE_WINDOW_START=09:00`
- `KEYWORD_GRAPH_CTS_PROBE_WINDOW_END=21:00`
- `KEYWORD_GRAPH_CTS_PROBE_TIMEZONE=Asia/Shanghai`
- No fixed daily cap; at 1 RPS over 12 hours the natural maximum is about 43200 requests/day.

Unattended overnight execution must not run real CTS because the permitted window is 09:00-21:00. It may run fake CTS tests and dry-run builders.

## Data Inputs

First version bootstrap corpus:

- 9530 public mainland China JD samples previously identified locally.

The implementation must also support small JSONL fixtures for tests. Full production data does not need to be committed to git.

## Governance

Human review is scarce. The system should use:

- Automatic blocking for company-like and department-like surfaces.
- Conservative non-merge behavior when alias evidence is weak.
- CSV sampling report for human reading.
- JSONL sampling results for machine replay.
- Maximum expected human time: 10 minutes/day.

No UI is required for sampling.

## Feedback

SeekTalent feedback is first local-only:

- Query-level aggregated artifact only.
- No automatic upload.
- No candidate-level data.
- Cross-machine transfer or upload requires later data-export decision.

## Milestones

### M0: Project Scaffold

Create a real Python package project with test and lint commands.

Acceptance:

- `python -c "import seektalent_keyword_graph"` succeeds.
- `pytest` succeeds.
- `ruff check .` succeeds.
- Package metadata name is `seektalent-keyword-graph`.
- No real CTS call exists.

### M1: Runtime Contract and Snapshot Reader

Implement Pydantic contracts, `KeywordGraph.open`, metadata validation, concept/surface lookup, and fallback warnings.

Acceptance:

- Small fixture snapshot opens read-only.
- Missing snapshot raises typed error.
- Unsupported schema raises typed error.
- Lookup tests pass.
- `build_query_plan` returns deterministic response for fixture input.

### M2: JD Import and Keyword Extraction

Implement JSONL JD import, section splitting, and rule/dictionary extraction.

Acceptance:

- Fixture JD JSONL imports into build DB.
- Mentions trace back to JD and section.
- Company/department-like samples are blocked or flagged.
- Extraction report is generated.

### M3: Surface, Concept, Relation, Co-occurrence

Implement normalization, concept clustering, alias relations, and co-occurrence edges.

Acceptance:

- `k8s` and `Kubernetes` can map to one concept through relation evidence.
- `Vue` and `React` do not auto-merge.
- Co-occurrence edges are generated from fixture data.
- Sampling CSV and JSONL are generated.

### M4: Internal CTS Count Probe

Implement fake CTS probe fully and real CTS probe behind explicit builder gate.

Acceptance:

- Fake CTS tests cover success, zero, timeout, 429, 5xx, and auth error.
- Real CTS code uses `page=1`, `pageSize=1`, and reads only `data.total`.
- Real CTS command refuses to run outside 09:00-21:00 unless `--dry-run`.
- Runtime package does not import builder CTS client.

### M5: Snapshot Build and Query Bundle MVP

Build runtime snapshot from build DB and implement bundle selection.

Acceptance:

- Snapshot validates schema, manifest, checksum, and privacy rules.
- Query bundles include `anchor`, `precision`, `alias_probe`, `exploration`, or `fallback` as applicable.
- Response includes lineage, reason codes, rejected surfaces, and warnings.
- Replay evaluation report is generated.

### M6: SeekTalent Integration Contract

Prepare dependency-facing adapter docs and consumer contract examples; do not modify SeekTalent unless explicitly requested.

Acceptance:

- Example request/response files are stable.
- Contract tests can be consumed by SeekTalent.
- Env var names use `SEEKTALENT_KEYWORD_GRAPH_*`.
- Failure mode documents `keyword_graph_unavailable`.

### M7: Release Hardening

Add release checks, build reports, rollback docs, and artifact validation.

Acceptance:

- Wheel builds.
- Snapshot artifact validation rejects secrets, candidate lists, and oversized compressed snapshots.
- Release checklist exists.
- Rollback instructions exist.

## Execution Strategy

For a long Codex Goal run:

1. Execute slices in order.
2. Commit after each slice that passes its checks.
3. If a slice is blocked by unavailable real CTS, skip only that real-CTS step and continue fake/dry-run work.
4. Stop only on repeated blocker, test failure that cannot be resolved, or completion.
5. Prefer finishing a smaller verified slice over creating broad unverified code.
