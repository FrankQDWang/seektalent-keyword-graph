# Execution Contract

This file closes the main loopholes that a long autonomous build could exploit.
It is a product execution contract for the keyword graph builder goal.

## Preflight

Before implementation or production-candidate execution, run and record these
checks:

```bash
test -r /Users/frankqdwang/MLE/gbrain-reference/src/core/by-mention.ts
test -r /Users/frankqdwang/MLE/gbrain-reference/docs/ethos/THIN_HARNESS_FAT_SKILLS.md
test -r /Users/frankqdwang/MLE/jd-graph/config/sources/bytedance_jobs_2026_05_12.json
test -r /Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl
wc -l /Users/frankqdwang/MLE/jd-graph/data/derived/company=bytedance/source=jobs_bytedance/factual_jobs_mainland.jsonl
```

The `wc -l` output for the primary completion corpus must be `9530` unless a
newer manifest is explicitly documented. If any preflight check fails, report a
blocker. Do not fall back to fixtures, mocks, or synthetic samples and claim
completion.

The 9864-line selected/deduplicated JSONL is an auxiliary comparison input, not
the primary completion corpus. The primary completion corpus is the 9530-line
mainland JD JSONL.

## Product-Owned Thin Harness And Rich Skills

Thin harness and rich skills are product architecture concepts for this package,
not Codex development tooling.

Thin harness means the builder exposes deterministic commands that run defined
steps:

- import corpus manifest;
- build gazetteer;
- extract mentions;
- infer relations;
- propose LLM candidates;
- review candidates;
- probe providers;
- build snapshot;
- validate snapshot;
- emit quality gate and readiness artifacts.

Rich skills means the product owns versioned domain procedures, prompts, rules,
review rubrics, and release gates that guide those commands. They should be
stored as repository artifacts and referenced by builder reports. They are not
`.agents` Codex skills, and they must not depend on Codex memory.

Future implementation may choose exact paths, but the product artifacts must
cover at least:

- schema authoring;
- corpus import;
- surface taxonomy evolution;
- relation rule authoring;
- LLM candidate review;
- provider recall probing;
- anti-hack review;
- snapshot release.

## LLM Provider Contract

LLM assistance belongs to the offline builder only. It is not Codex assistance
and not runtime behavior.

The builder must support an OpenAI-compatible LLM provider configuration. The
first intended provider is Alibaba Cloud Bailian. Required builder-only config
fields:

- provider name;
- OpenAI-compatible base URL;
- model name;
- API key environment variable name;
- timeout;
- retry limit;
- budget limit;
- prompt version;
- dry-run flag.

LLM credentials must never be read by runtime code, inspector UI, or SeekTalent
integration paths.

## Release Candidate Surfaces

The build must produce a release candidate surface artifact:

```text
artifacts/release-candidates/<builder_run_id>.release_candidate_surfaces.jsonl
```

Each row must include:

- `surface_id`;
- `query_text`;
- `surface_type`;
- `concept_id`;
- `evidence_count`;
- `jd_df`;
- `serving_status`;
- `provider_required`;
- `inclusion_reason`;
- `exclusion_reason`;
- `review_status`.

`docs/readiness-report.md` and the quality gate artifact must record:

- extracted surface count;
- serving surface count;
- release-candidate CTS surface count;
- excluded count by reason;
- release candidate artifact path and sha256.

The release-candidate CTS surface count must not be artificially minimized. If
it is suspiciously small relative to serving surfaces, the gate must be failed or
marked incomplete unless a structured manual exception is recorded.

## Subagent Review Artifacts

Clean-context subagent reviews must write artifacts under:

```text
docs/reviews/
```

Required artifacts:

- `docs/reviews/graph-content-review-<builder_run_id>.md`;
- `docs/reviews/anti-hack-review-<builder_run_id>.md`;
- `docs/reviews/generalization-review-<builder_run_id>.md`;
- `docs/reviews/recall-readiness-review-<builder_run_id>.md`.

Each artifact must contain:

- reviewer context statement;
- artifact paths inspected;
- sample source;
- rows inspected;
- blocking findings;
- non-blocking findings;
- verdict;
- reviewer identity or subagent ID;
- created time.

If any artifact is missing or any verdict has blocking findings, the goal is not
complete.

## Real CTS Human Gate Artifact

Real CTS probing requires a gate artifact before the probe starts:

```text
artifacts/cts-gates/<cts_run_id>.gate.json
```

Required fields:

- fixed approval token: `APPROVE_REAL_CTS_PROBE`;
- `cts_run_id`;
- `builder_run_id`;
- `operator`;
- `approved_at`;
- `expires_at`;
- `provider`;
- `surface_count`;
- `scope_sha256`;
- `gate_artifact_sha256`.

The probe job table and readiness report must record the gate artifact path and
sha256. A free-text statement such as "human approved" is not enough.

## Anti-Hack First Slice

The first implementation slice must add guard tests or scanners before building
new behavior. These guards must check:

- runtime does not import builder, CTS, provider clients, LLM clients, or
  SeekTalent;
- production extraction path does not rely on fixture-specific branches;
- production extraction path does not use hardcoded famous terms as the primary
  source;
- production code does not return fixed constant outputs for contracts;
- broad `except Exception` does not hide failures or mark success;
- readiness report cannot claim completion without command outputs and artifact
  IDs;
- mock, fake, dry-run, or fixture CTS observations cannot satisfy final
  completion.

These guards must be red before implementation if the protected behavior is
missing, and green before later slices proceed.

## GBrain Adoption Evidence

`docs/readiness-report.md` must include a `GBrain reference adoption` section.
For each referenced GBrain file, record:

- file read;
- principle adopted;
- keyword graph implementation artifact;
- test or report proving adoption.

Required mappings include:

- `by-mention.ts` -> longest-match mention extraction;
- `link-extraction.ts` -> context-window relation inference;
- `schema-pack/base/gbrain-base.yaml` -> taxonomy/rule config schema;
- `schema-pack/link-inference.ts` -> pack-aware relation rule evaluation;
- `schema.sql` -> provenance-backed graph projection.
