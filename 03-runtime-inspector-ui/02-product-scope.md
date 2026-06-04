# Product Scope

## Primary User

The first user is an internal developer or reviewer validating a generated runtime snapshot before or after it is consumed by SeekTalent.

They want to answer simple questions quickly:

- Does this query term exist in the graph?
- What recall count did the selected provider observe?
- When was that count observed?
- Is the term zero-recall, too wide, stale, unknown, or healthy?
- What aliases or near terms does the graph suggest?
- Which candidate term is better for retrieval?

## First Screen

The UI should open directly to the inspector workflow, not to a marketing page.

Required controls:

- snapshot path display;
- manifest path display;
- snapshot metadata summary;
- provider selector;
- query mode selector;
- query text input;
- max alternatives input or default;
- analyze button.

Required result areas:

- input term observation;
- recommendation summary;
- alternatives table;
- warnings;
- provenance/evidence details.

## Data Display

For the input query, show:

- `query_text`;
- matched surface id, if any;
- provider;
- query mode;
- total;
- status;
- recall bucket;
- observed at;
- observation id;
- evidence ref.

For each alternative, show:

- candidate query text;
- relation type;
- confidence;
- source concept id;
- source surface id;
- target surface id;
- provider;
- total;
- status;
- recall bucket;
- observed at;
- evidence type/ref.

For recommendations, show:

- action;
- source query;
- recommended query, if different;
- reason code;
- human-readable reason;
- evidence observation ids.

## Packaging Scope

The first UI should stay in the existing package if it can be implemented without heavy dependencies.

Acceptable:

- Python standard library HTTP server;
- static HTML/CSS/JS files;
- package data for static assets;
- lazy import of UI modules only when the UI command runs.

Avoid:

- React/Vite build artifacts;
- Streamlit;
- Gradio;
- FastAPI/Starlette unless there is a concrete reason;
- any dependency that materially increases install size for SeekTalent runtime users.

If a later UI version needs heavy dependencies, revisit a split such as `seektalent-keyword-graph-ui` or a `[ui]` extra.
