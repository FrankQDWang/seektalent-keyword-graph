# Query Recall Placement

SeekTalent query term pool generation happens first. Query Recall Optimization
runs next inside this package. provider retrieval happens after SeekTalent
accepts or merges the optimized term-pool actions.

Do not modify the SeekTalent main project for this integration slice. The only
contract is the package API and JSON schemas in `contracts/query-recall/`.

## Query Recall Optimization

The consumer calls `KeywordGraph.open(...)` and then either
`analyze_query_recall(QueryRecallRequest(...))` or
`optimize_query_terms(QueryRecallRequest(...))`. Both methods read provider-aware
observations from the local snapshot. They do not call live providers and do not
read CTS environment variables.

Runtime defaults come from:

- `SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER`
- `SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES`

## Request

`contracts/query-recall/request.example.json` is fixture-derived from the
SeekTalent term pool shape:

- `provider` identifies the provider whose local observations should be used.
- `query_terms` carry term-pool items with `text`, `strength`, and
  `source=query_term_pool`.
- `query_mode` defaults to `keyword`.
- `max_alternatives` caps returned graph alternatives.
- `max_precision_companions` caps companion terms for too-wide inputs.

## Response

`contracts/query-recall/response.example.json` is from `kg-eval-fixture` and
contains provider-aware observations for `cts`, graph alternatives with their
own observations, term-pool recommendations, optimized terms, warnings, and
lineage.

Term-pool actions:

- `keep`: retain the original term.
- `replace`: replace a weak term with a healthier graph alternative.
- `add_precision_companion`: add a companion term to narrow a too-wide input.
- `score_only`: keep the term as scoring context instead of retrieval text.
- `fallback`: preserve unmatched input under fail-open behavior.

Provider behavior:

- `zero`, `too_wide`, `too_narrow`, `stale`, and `unknown` observations are
  non-fatal and returned as warnings or recommendations.
- Unsupported providers fail the call; SeekTalent decides whether to fail open.
- All evidence is lineage-backed by snapshot rows such as
  `snapshot:kg-eval-fixture`, `surface:*`, `concept:*`, and `observation:*`.

## Compatibility

Existing response fields remain stable for `query-recall-response-v1`. Additive
optional fields require schema and example updates. Breaking changes require a
new schema version and migration notes for consumers.
