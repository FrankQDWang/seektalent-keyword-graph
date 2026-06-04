# Completion Criteria

This goal is complete only when the production graph has been built and reviewed
from the real local JD corpus. Passing mocks, fixtures, or synthetic examples is
not completion evidence.

## Real Corpus Build

Completion requires importing the already-available local JD corpus of roughly
9000+ JD documents through a production corpus manifest.

The currently known local corpus is:

- source config:
  `/Users/frankqdwang/MLE/jd-graph/config/sources/bytedance_jobs_2026_05_12.json`;
- primary mainland JD JSONL:
  `/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl`;
- expected mainland JD count: 9530;
- canonical selected/deduplicated JSONL:
  `/Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/normalized_factual_jobs_selected_dedup.jsonl`;
- expected selected/deduplicated count: 9864;
- raw collection manifest:
  `/Users/frankqdwang/MLE/jd-graph/data/raw/company=bytedance/source=jobs_bytedance/captured_date=2026-05-12/collection_manifest.json`.

The source config records `run_id` as `bytedance_jobs_2026_05_12_win_sync` and
`captured_date` as `2026-05-12`. The primary completion corpus is the 9530-line
mainland JD JSONL unless a newer manifest is explicitly documented.

Required evidence:

- manifest path;
- corpus ID and version;
- expected JD count;
- actual imported JD count;
- skipped and deduplicated counts with reasons;
- clean build DB path;
- build command;
- build started and finished timestamps;
- source corpus hash or per-file content hash policy;
- privacy scan result.

Before any production-candidate work, the preflight commands in
`08-execution-contract.md` must pass and be recorded. If the primary mainland JD
JSONL is missing or does not contain 9530 lines, the run is blocked.

The production graph must be built from a clean database. Every new production
build, evaluation run, and regression investigation must delete or recreate the
previous build DB before import. Reusing a dirty DB, fixture DB, or previous
failed build DB is a blocking failure.

## Independent Subagent Reviews

After graph construction, use subagent-driven review with fresh, clean-context
subagents. Reviewers must not rely on this conversation or prior local memory;
they must inspect the built artifacts, reports, sampled graph rows, and code.

Required review lanes:

- Graph content review: sampled extracted keywords must be suitable resume
  search terms, not generic noise, company names, department labels, policy
  boilerplate, or JD-only prose fragments.
- Anti-hack review: inspect code, tests, reports, and artifacts for
  fixture-specific branches, fixed outputs, placeholder success, hidden broad
  exceptions, fake readiness, or hardcoded examples.
- Generalization review: handwritten rules must be broad, evidence-based, and
  domain-general. Rules must not target only a few specific fields, companies,
  test keywords, or famous technology nouns.
- Recall readiness review: accepted surfaces must have provider-aware recall
  observation readiness and clear action semantics for SeekTalent query recall
  optimization.

Each subagent must write a review artifact or summary that is linked from
`docs/readiness-report.md`. If any reviewer reports a blocking issue, the goal
is incomplete until the issue is fixed and the graph is rebuilt from a clean DB.

Review artifacts must follow the path and field contract in
`08-execution-contract.md`.

## Real CTS Completion Gate

Final completion requires real CTS probing for every release-candidate keyword
surface that will be included in the serving snapshot for CTS recall
optimization.

The release-candidate surface set must be materialized before CTS probing and
must follow `08-execution-contract.md`. It must not be manually shrunk to make
CTS coverage easier.

For each probed surface, the snapshot must store:

- provider: `cts`;
- query text;
- query mode;
- total;
- status;
- recall bucket;
- observed time;
- provider/API version when available;
- probe job ID;
- evidence/provenance.

Fake, mock, dry-run, or fixture CTS observations are allowed only for lower-level
development checks. They are not acceptable as final completion evidence and
must not be cited as proof that the production graph is ready.

Real CTS calls must still be explicitly gated by a human immediately before the
probe run. If the gate is not granted, the correct final status is incomplete,
not complete. No unattended real CTS calls are allowed.

The human gate must be represented by the CTS gate artifact defined in
`08-execution-contract.md`; a free-text readiness note is not enough.

The real CTS probe flow must use rate limits, retry policy, resumable jobs,
dedupe, and clear failure reporting. Partial CTS coverage cannot be hidden; it
must be reported as incomplete unless explicitly accepted in the readiness
report with the exact excluded surfaces and reasons.

## Final Definition Of Done

The goal is done only when all of these are true:

- the local 9000+ JD corpus was imported through a production manifest;
- the imported corpus path and count matched the documented local ByteDance
  corpus or a newer explicitly documented replacement manifest;
- every build/evaluation cycle used a clean build DB;
- graph extraction, relation inference, and snapshot build succeeded from the
  real corpus;
- quality gate artifact followed `07-quality-gate-schema.md` and passed;
- release-candidate surface artifact followed `08-execution-contract.md`;
- independent clean-context subagent reviews found no blocking graph quality,
  anti-hack, or generalization issues;
- real CTS observations were collected for every release-candidate CTS keyword
  surface after explicit human gate;
- the bundled snapshot was rebuilt with those real CTS observations;
- runtime query recall optimization works against the rebuilt bundled snapshot;
- inspector UI can query the same bundled snapshot;
- wheel install smoke test passed;
- `docs/readiness-report.md` records commands, artifact paths, snapshot ID,
  CTS run ID, review artifacts, and known risks.

If any item is missing, the implementation may be useful progress, but the goal
must not be marked complete.
