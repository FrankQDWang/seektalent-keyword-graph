# Implementation Boundaries

## Hard Prohibitions

The next goal must not use any of the following shortcuts:

- no fixture-specific branches;
- no hardcoded production whitelist like `React`, `Kafka`, `Python`, or
  `Kubernetes` as the primary extraction source;
- no fixed constant outputs to satisfy contract tests;
- no placeholder APIs that return empty success responses;
- no fake graph edges without evidence;
- no fake provider observations in production artifacts;
- no production-candidate build without a corpus manifest;
- no production-candidate build that skips the local 9000+ JD corpus;
- no production/evaluation rerun that reuses a dirty build DB;
- no release snapshot built from unreviewed LLM candidates;
- no bypassing graph quality gates to make a build appear complete;
- no claiming completion without independent clean-context subagent reviews;
- no claiming final CTS coverage from mock, fake, fixture, or dry-run data;
- no broad exception swallowing that hides build failures;
- no tests that only prove mocks call mocks;
- no skipping real snapshot packaging validation;
- no changing runtime to import builder, CTS, provider clients, LLM clients, or
  SeekTalent;
- no changing package boundaries to make the implementation easier.

Fixtures are allowed only for tests. They must not be the basis of the released
graph.

## Corpus Manifest Boundary

A production-candidate build must be manifest-driven. The builder must not infer
production input data from an arbitrary local directory or from whatever files
happen to exist on disk.

The manifest is the boundary between local experimentation and a releasable
graph build. It must identify the corpus, expected document counts, historical
query evidence, exclusion policy, privacy scan policy, source ownership, and
build mode.

Fixture and dry-run manifests are allowed, but their mode must be explicit and
must propagate into build reports, snapshot metadata, and readiness output.

Each production-candidate build or evaluation rerun must start from a clean build
DB. The command path should either create a new DB path or explicitly delete and
recreate the old DB. Dirty DB reuse is a blocking failure because it can hide
stale surfaces, stale relations, and stale provider observations.

## Production Builder Boundary

The builder is centralized and internal. It may read builder-only configuration,
builder-only provider credentials, local corpora, reviewed taxonomies, and LLM
configuration when explicitly enabled.

The builder must default to safe execution:

- fake or dry-run provider probing unless a human explicitly gates real probes;
- no unattended real CTS calls;
- no provider credentials read from runtime paths;
- clean build DB creation for production graph builds;
- fixture build DBs only for tests and examples;
- build reports that distinguish fixture, dry-run, fake, and production data.

For final completion, provider recall observations for CTS must come from a real
CTS probe run after explicit human gate. Fake, mock, fixture, and dry-run CTS
rows may exist for lower-level tests, but they cannot be used as final readiness
evidence.

## Runtime Boundary

Runtime is user-side package behavior. It must:

- read only bundled or explicitly supplied runtime snapshots;
- perform local deterministic lookup and ranking;
- never perform network I/O;
- never call CTS, Liepin, Boss, or LLMs;
- never read `KEYWORD_GRAPH_CTS_*`;
- never import builder or CTS modules;
- never import SeekTalent.

## LLM Boundary

LLM assistance is allowed only in offline builder workflows. It must be
explicitly configured and auditable.

LLM assistance is a product-builder integration, not Codex assistance. The
builder must support builder-only OpenAI-compatible provider configuration, with
Alibaba Cloud Bailian as the first intended provider. Runtime, inspector UI, and
SeekTalent integration paths must never read LLM credentials or call LLM APIs.

LLM outputs must include:

- input document/window ID;
- evidence span or snippet;
- proposed surface;
- proposed type;
- proposed relation when applicable;
- confidence;
- model name;
- prompt version;
- created time;
- review or validation status.

Unreviewed LLM output must not silently enter a release snapshot.

Accepted LLM candidates must be traceable from runtime graph output back to the
reviewed candidate, evidence window, model, and prompt version. Rejected
candidates must remain available for audit and sampling reports.

## Graph Quality Gate Boundary

Production readiness requires quality evidence, not just passing unit tests. The
builder must produce reports that let a reviewer inspect extraction quality,
merge quality, relation quality, provider observation coverage, and replayed
query recall optimization behavior.

At minimum, the release gate must fail or report incomplete when:

- corpus manifest validation failed;
- privacy scan was not run;
- extraction counts are missing by surface type;
- relation counts are missing by relation type;
- provider observation coverage is missing for declared providers;
- CTS observations for release-candidate CTS keyword surfaces are not from a
  real gated CTS probe;
- LLM-sourced accepted candidates lack review or validation status;
- independent clean-context subagent reviews were not completed or reported;
- bundled snapshot smoke test was not run from an installed wheel.

Subagent reviews must inspect the built graph and implementation artifacts from
fresh context. They must explicitly check keyword usefulness for resume search,
anti-hack compliance, and whether handwritten rules are generalizable rather
than tailored to specific domains or named test terms.

Quality gate output must follow `07-quality-gate-schema.md`, and release
candidate surfaces, CTS gate artifacts, subagent review artifacts, anti-hack
first-slice guards, and GBrain adoption evidence must follow
`08-execution-contract.md`.

## Definition of Done

The future implementation is done only when the full path works end to end:

- real JD corpus import into a clean build DB;
- local 9000+ JD corpus completion evidence;
- manifest-backed corpus validation;
- extraction and relation inference with evidence;
- graph quality report with sampling and replay evidence;
- machine-readable quality gate artifact;
- release-candidate surface artifact;
- independent clean-context subagent review artifacts;
- real gated CTS observation storage for release-candidate CTS keyword surfaces;
- snapshot build and validation;
- bundled artifact packaging;
- runtime open from installed wheel;
- query recall optimization over the bundled snapshot;
- inspector UI query over the same bundled snapshot;
- readiness report with commands and artifact IDs;
- tests and lint passing through `uv run`.

Anything less must be reported as incomplete.
