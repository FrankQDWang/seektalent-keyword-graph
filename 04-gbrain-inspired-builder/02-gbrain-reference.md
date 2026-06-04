# GBrain Reference Notes

## Thin Harness, Rich Skills

GBrain keeps deterministic execution in a thin CLI/core harness and pushes
judgment, routing, domain process, and quality standards into rich skills and
schema packs.

Reference files:

- `/Users/frankqdwang/MLE/gbrain-reference/docs/ethos/THIN_HARNESS_FAT_SKILLS.md`
- `/Users/frankqdwang/MLE/gbrain-reference/skills/RESOLVER.md`
- `/Users/frankqdwang/MLE/gbrain-reference/skills/ingest/SKILL.md`
- `/Users/frankqdwang/MLE/gbrain-reference/skills/query/SKILL.md`
- `/Users/frankqdwang/MLE/gbrain-reference/docs/guides/skill-development.md`
- `/Users/frankqdwang/MLE/gbrain-reference/docs/skillpack-anatomy.md`

Translate this pattern into the keyword graph builder:

- CLI commands should do deterministic execution only.
- Domain decisions should live in versioned schema, rules, eval fixtures, and
  rich skill docs.
- Agent workflows should read the relevant skill before changing schema,
  extraction, relation rules, LLM prompts, provider probing, or snapshot release
  logic.

## Graph Extraction Lessons

GBrain's base graph construction is not an LLM-first black box. It combines:

- explicit link extraction;
- gazetteer/by-mention scanning over known entities;
- longest-match entity detection;
- local context windows around mentions;
- deterministic relation inference rules;
- frontmatter/schema-driven edges;
- provenance-aware reconciliation into a graph projection.

Reference files:

- `/Users/frankqdwang/MLE/gbrain-reference/src/core/operations.ts`
- `/Users/frankqdwang/MLE/gbrain-reference/src/core/link-extraction.ts`
- `/Users/frankqdwang/MLE/gbrain-reference/src/core/by-mention.ts`
- `/Users/frankqdwang/MLE/gbrain-reference/src/core/extract-ner.ts`
- `/Users/frankqdwang/MLE/gbrain-reference/src/schema.sql`

Keyword graph translation:

- Use JD sections and local text windows as evidence units.
- Build a gazetteer from real surfaces, historical query terms, curated
  taxonomies, reviewed LLM proposals, and provider observations.
- Use longest-match scanning and offsets instead of broad regex alternation.
- Confirm relation types from local windows, not from global co-occurrence only.
- Persist evidence spans, snippets, source document IDs, rule IDs, confidence,
  and extraction version.

## Schema Pack Lessons

GBrain uses schema packs to declare entity types and relation inference behavior.

Reference files:

- `/Users/frankqdwang/MLE/gbrain-reference/src/core/schema-pack/base/gbrain-base.yaml`
- `/Users/frankqdwang/MLE/gbrain-reference/src/core/schema-pack/base/gbrain-base-v2.yaml`
- `/Users/frankqdwang/MLE/gbrain-reference/src/core/schema-pack/link-inference.ts`

Keyword graph translation:

- Define surface/entity types outside Python code.
- Define allowed relation types and relation-rule ownership outside ad hoc code.
- Version schema/rules and include the versions in build reports and snapshots.
- Treat user-visible query behavior as a contract, not an implementation detail.

## LLM Boundary

GBrain uses LLMs for synthesis, query expansion, schema suggestion, atom/concept
synthesis, and selected chunking workflows. Its base auto-link graph extraction
is deterministic.

Keyword graph translation:

- LLM may propose candidate surfaces, entity types, aliases, abbreviations,
  equivalent terms, and evidence spans during offline builder runs.
- LLM output must be reviewed or validated before entering the release snapshot.
- LLM calls must have explicit config, dry-run support, budgets, retry caps,
  eval fixtures, and readiness reporting.
- Runtime must never call LLMs or providers.
