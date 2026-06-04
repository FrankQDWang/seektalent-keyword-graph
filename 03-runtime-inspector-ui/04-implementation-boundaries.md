# Implementation Boundaries

## Hard Boundaries

- Do not call real CTS from the UI.
- Do not call Liepin, Boss, or any live provider from the UI.
- Do not read `KEYWORD_GRAPH_CTS_*` in UI or runtime paths.
- Do not import `seektalent_keyword_graph.builder` or `seektalent_keyword_graph.cts` from runtime/UI query handling.
- Do not import SeekTalent.
- Do not modify the SeekTalent main project.
- Do not write or mutate runtime snapshot artifacts.
- Do not introduce heavy UI dependencies in the first version.

## Runtime Boundary

The UI should use the public runtime surface:

- `KeywordGraph.open(snapshot, manifest)`;
- `analyze_query_recall`;
- `optimize_query_terms`;
- public contract models.

It should not reach directly into builder internals or CTS clients.

## Server Boundary

The first implementation should prefer Python standard library server primitives.

If a non-stdlib server dependency is proposed, the goal execution should justify why it is necessary and measure the packaging impact.

Default server behavior:

- bind host: `127.0.0.1`;
- choose a configurable port;
- serve static assets from package data;
- expose minimal JSON endpoints;
- keep the opened snapshot read-only;
- shut down cleanly on interrupt.

Command behavior:

- implement the first version as `keyword-graph inspect-ui` on the existing console script;
- do not add a second console script unless the implementation proves the existing CLI cannot support the command cleanly.

## API Boundary

Minimal local API:

- `GET /api/meta`
  - returns snapshot id, schema version, built_at, provider sources, policy version.
- `POST /api/query-recall`
  - accepts provider, query text, query mode, max alternatives.
  - returns the public query recall response or a stable error object.
- `GET /`
  - returns the static inspector page.

Stable local API errors should use this shape:

```json
{
  "error": {
    "code": "unsupported_provider",
    "message": "Provider is not available in this snapshot.",
    "details": {}
  }
}
```

Initial error codes should cover `unsupported_provider`, `no_match`, `matched_without_observation`, `invalid_request`, `invalid_snapshot`, and `internal_error`.

## Security Boundary

This is a local developer tool, not an internet-facing service.

- Bind to localhost by default.
- Do not add remote access by default.
- Do not expose filesystem browsing beyond explicit snapshot/manifest paths supplied at startup.
- Do not log secrets or environment contents.

## Documentation Boundary

Do not create Superpowers spec or plan files for this preparatory documentation step.

During the future Codex goal, Codex may decide whether to use any workflow, but the canonical input should be the goal brief and goal prompt in this directory plus the existing repository docs.
