# Product Scope

## In Scope

The full builder product must support the following end-to-end path:

1. Define and validate a production corpus manifest for the already-available
   local 9000+ JD corpus and historical query evidence.
2. Import the manifest-declared corpus into a clean build DB.
3. Split JD text into structured sections and evidence windows with offsets.
4. Build and evolve a schema-owned taxonomy of keyword surface types.
5. Extract candidate surfaces through deterministic and offline-assisted routes.
6. Normalize surfaces and cluster them into concepts.
7. Infer graph relations from local evidence windows and corpus statistics.
8. Store provider-aware recall observations by provider, query mode, surface,
   status, total, recall bucket, observed time, and provenance.
9. Generate sampling reports and graph quality reports for human review.
10. Build a runtime SQLite snapshot and manifest.
11. Validate schema, checksums, privacy, provider coverage, query recall
    behavior, and wheel packaging.
12. Prove runtime and inspector UI can query the bundled snapshot locally.
13. Complete the hard acceptance criteria in `06-completion-criteria.md`,
    including clean-context subagent reviews and real CTS observations.
14. Produce machine-readable quality gate, release-candidate, CTS gate, and
    review artifacts defined in `07-quality-gate-schema.md` and
    `08-execution-contract.md`.

## Required Corpus Manifest

Production builds must be driven by a manifest, not by implicit local paths or
fixture assumptions. The manifest should include at least:

- corpus ID and version;
- build mode: fixture, dry-run, fake-provider, or production-candidate;
- JD source paths and historical query evidence paths;
- expected document counts and optional sampling windows;
- source type and source ownership;
- content hash policy;
- language and domain coverage notes;
- privacy scan policy;
- excluded sources and exclusion reasons;
- created time and build operator.

The builder must fail clearly when a production-candidate build has no manifest,
the document count materially mismatches the manifest, or privacy scan policy is
missing.

The currently known local bootstrap corpus is the ByteDance public JD corpus
captured on 2026-05-12 in `/Users/frankqdwang/MLE/jd-graph`:

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

Future runs may add corpora, but this known corpus must remain an explicit
production-candidate acceptance input until it is replaced by a newer documented
manifest.

## Required Surface Types

The next implementation should define a versioned taxonomy rather than a
hardcoded Python list. The first complete taxonomy should cover at least:

- skill;
- tool;
- framework;
- programming language;
- platform;
- cloud service;
- database or storage system;
- certificate;
- role or job family;
- domain;
- industry;
- method or methodology;
- business function;
- seniority;
- query modifier or precision companion.

The exact names can change during implementation, but each type must have clear
ownership, examples, extraction sources, and query-safety behavior.

## Required Relation Types

The graph must support at least:

- normalized surface;
- alias;
- abbreviation;
- equivalent;
- version variant;
- co-occurrence;
- precision companion;
- broader or narrower related term;
- provider recall risk relation;
- fallback or score-only relation.

Every relation must include `relation_type`, `confidence`, source and target
surface IDs, concept IDs where applicable, evidence/provenance, and extraction
rule or model version.

## Required Recall Behavior

Provider-aware recall observations remain a first-class product requirement.
The builder must support CTS first, while keeping the schema provider-aware for
Liepin, Boss, and future providers.

Runtime must expose observations for:

- exact input query;
- normalized query;
- alias, abbreviation, equivalent, and related alternatives;
- zero recall;
- too wide;
- too narrow;
- stale;
- unknown;
- unsupported provider;
- matched surface without provider observation.

## Required Quality Gates

The next implementation must make graph quality measurable before release. At
minimum, readiness evidence must report:

- corpus import counts, dedupe counts, skipped document counts, and language
  distribution;
- extraction coverage by surface type and JD section type;
- high-frequency generic-term rejects;
- ambiguous or risky surfaces requiring review;
- alias, abbreviation, equivalent, and version-variant merge samples;
- bad-merge and over-merge warnings;
- relation confidence distribution by relation type;
- provider observation coverage by provider and query mode;
- zero, too-wide, too-narrow, stale, and unknown observation counts;
- query recall optimization replay cases for representative input term pools;
- reviewer decisions or validation status for any LLM-sourced candidates.

Release must not be called production-ready if these reports are absent or
obviously fixture-only.

The quality gate is release-blocking. A production-candidate build must fail or
be marked incomplete when any of these conditions are true:

- no valid production corpus manifest was used;
- manifest-declared document counts materially differ from imported counts
  without an explicit exclusion record;
- privacy scan did not run or found forbidden release data;
- extraction coverage by surface type and JD section type is missing;
- relation counts and confidence distributions by relation type are missing;
- provider observation coverage is missing for any declared provider/source;
- query recall optimization replay cases were not run against the built
  snapshot;
- LLM-sourced accepted candidates lack review or validation status;
- bundled snapshot was not opened from an installed wheel;
- readiness report does not include the exact verification commands and artifact
  IDs.
- independent clean-context subagent reviews were not run against the built
  graph and implementation artifacts;
- final CTS observations are fake, mocked, dry-run, fixture-derived, or missing
  for release-candidate CTS keyword surfaces.

Numeric thresholds may evolve, but every threshold or manual-review exception
must be recorded in the readiness report. Silent pass-through is not allowed.

Mock, fake, fixture, and dry-run results may support lower-level engineering
tests, but they are not acceptable completion evidence for the production graph.

Quality reporting must follow `07-quality-gate-schema.md`; free-text reports
alone are not acceptable production-readiness evidence.

## Required LLM Candidate Review Gate

LLM assistance is allowed only as an offline candidate proposal path. LLM output
must be stored separately from accepted graph facts until reviewed or validated.

LLM assistance is performed by this project's offline builder through
builder-only provider config. The first intended provider is Alibaba Cloud
Bailian through an OpenAI-compatible endpoint. This does not mean using Codex as
the LLM engine.

Required candidate fields:

- candidate ID;
- source document/window ID;
- evidence span or snippet;
- proposed surface text and normalized text;
- proposed surface type;
- proposed relation type when applicable;
- target surface or concept when applicable;
- confidence;
- model name;
- prompt version;
- created time;
- review or validation status;
- reviewer or validator identity when accepted.

Only accepted or validated candidates may enter concept, surface, relation, or
snapshot projection tables.

## Out of Scope

- Replacing SeekTalent requirement extraction.
- Importing or modifying the SeekTalent main project.
- Runtime live probing of CTS, Liepin, Boss, or other providers.
- Runtime LLM calls.
- User-side graph construction as the default product mode.
- Claiming production readiness without a manifest-backed build and quality
  gate evidence.
- Claiming completion without the local 9000+ JD corpus build, clean-context
  subagent review, and real CTS observation pass required by
  `06-completion-criteria.md`.
- General-purpose knowledge graph features unrelated to query recall
  optimization.
