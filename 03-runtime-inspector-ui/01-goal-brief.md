# Local Snapshot Inspector UI Goal Brief

## Purpose

Build a local, read-only UI for manually inspecting a keyword graph runtime snapshot.

The UI should help a developer, operator, or product reviewer type a query term and see what the current package already knows about that term:

- whether the term exists in the snapshot;
- the provider-aware recall observation for the term;
- the observation time;
- the recall bucket and status;
- graph-backed near terms such as aliases, equivalents, normalized surfaces, and related surfaces;
- each near term's own provider recall observation and provenance;
- the runtime recommendation for whether to keep, replace, downrank, score-only, fallback, or add a probe/precision companion.

## Execution Model

This is intended to be executed as a future Codex goal. Do not pre-create a Superpowers spec or plan for it.

The goal prompt should give Codex the delivery objective, acceptance criteria, boundaries, and behavior controls. Codex may decide during that goal whether to use additional workflow skills, but this repository documentation should not prescribe a slice-by-slice Superpowers plan.

## Product Shape

First version should be a small local inspector bundled with the current package:

- a local server command, such as `keyword-graph inspect-ui` or `keyword-graph-ui serve`;
- static HTML/CSS/JS served by that command;
- JSON endpoints backed by the existing `KeywordGraph` runtime API;
- no live provider calls;
- no write path to snapshot artifacts.

## Non-Goals

- Do not build a hosted service.
- Do not add authentication.
- Do not add multi-user collaboration.
- Do not add graph editing.
- Do not add snapshot mutation.
- Do not call real CTS or other providers from the UI.
- Do not replace the existing CLI build pipeline.
- Do not split the package unless UI dependencies become materially heavy.
