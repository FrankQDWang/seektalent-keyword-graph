# Query Plan Contract

Query planning converts normalized requirement terms into deterministic,
graph-backed query bundles. The consumer calls `KeywordGraph.open(...)` and then
`build_query_plan(QueryPlanRequest(...))`.

## Request

`contracts/query-plan/request.example.json` is fixture-derived from
`kg-eval-fixture`. It sends requirement terms from the caller and can also carry
title, JD text, notes, `max_query_bundles`, and `include_exploration`.

Rules:

- `schema_version` is `query-plan-request-v1`.
- `request_id` is caller generated and echoed in the response.
- At least one of requirement terms, title, JD text, or notes must be non-blank.
- Requirement terms keep `text`, `strength`, and `source`; no provider
  credentials or CTS settings are accepted.

## Response

`contracts/query-plan/response.example.json` contains real fixture bundles:
`anchor`, `precision`, `alias_probe`, and `exploration`. It also contains
company-like and department-like rejections plus lineage pointing at
`snapshot:kg-eval-fixture`.

Response fields:

- `concept_sheet` explains matched concepts, selected surfaces, recall buckets,
  and confidence.
- `query_bundles` are ordered recommendations. SeekTalent may execute one or
  more bundles according to product policy.
- `rejected_surfaces` explains safe exclusions before query construction.
- `warnings` are non-fatal signals such as stale or unknown observations.
- `lineage` contains the input hash, snapshot schema version, selection policy
  version, and source refs needed for deterministic replay.

## Compatibility rules

The compatibility rules are additive:

- Consumers must ignore unknown warning codes only after a schema version bump or
  compatibility note.
- Existing fields keep their names, types, and meanings for
  `query-plan-response-v1`.
- New optional fields may be added only when strict contract tests and schemas
  are updated together.
- Removing or renaming fields requires a new schema version.
- Runtime responses are local-only and must not depend on live provider calls.
