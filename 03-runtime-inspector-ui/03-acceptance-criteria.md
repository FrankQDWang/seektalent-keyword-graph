# Acceptance Criteria

## Local Server

- The documented `keyword-graph inspect-ui` command starts the inspector UI from the installed package.
- The server binds to `127.0.0.1` by default.
- The command accepts `--snapshot` and `--manifest`.
- The command fails clearly when snapshot or manifest paths are missing, invalid, or fail validation.
- The command does not open any network provider connection.

## Static UI

- The browser UI loads from the local server without a frontend build step.
- A user can enter one query term.
- A user can select a provider available in the snapshot.
- A user can select query mode or use the default `keyword` mode.
- The page renders useful empty/error states for:
  - unsupported provider;
  - no matching surface;
  - matched surface without observation;
  - corrupt or unavailable snapshot.
- The page maps stable local API error objects into visible, non-overlapping UI states.

## Query Recall Result

For a real fixture snapshot, the UI displays the input term's:

- query text;
- provider;
- query mode;
- total;
- status;
- recall bucket;
- observed at;
- observation id;
- evidence ref when present.

## Alternatives and Recommendations

For a real fixture snapshot, the UI displays graph-backed alternatives and recommendations:

- alias/equivalent/related candidate terms;
- relation type;
- confidence;
- source concept id;
- source surface id;
- target surface id;
- evidence type/ref;
- candidate provider recall total/status/bucket/observed_at;
- action recommendations such as keep, replace, downrank, alias probe, precision companion, score-only, or fallback.

## Safety and Boundaries

- UI code path does not import builder or CTS modules during runtime query handling.
- UI code path does not read `KEYWORD_GRAPH_CTS_*`.
- UI code path does not call live CTS, Liepin, Boss, or any provider endpoint.
- UI code path does not write to snapshot, manifest, or gzip artifacts.
- Package import remains lightweight; UI is lazy-loaded only when the UI command runs.

## Verification

The goal should include tests or checks that cover:

- command help and startup validation;
- static asset serving;
- JSON API query against a fixture snapshot;
- HTTP-level JSON API checks for success responses and stable error objects;
- browser-level DOM or screenshot smoke check for a known fixture term such as `React` and at least one empty/error state;
- no runtime builder/CTS import regression;
- no CTS env read regression;
- no provider network I/O regression;
- package/wheel smoke verifies the UI command starts from an installed wheel and includes static assets.

Expected manual demo:

- Start the UI against a fixture snapshot.
- Query `React` with provider `cts`.
- See `React` as zero recall and `React.js` as an alias alternative with healthy recall.
