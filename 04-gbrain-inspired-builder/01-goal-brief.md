# Goal Brief

## Purpose

The next major product goal is to replace the current toy keyword extraction
path with a production-ready, GBrain-inspired offline graph builder.

The runtime and inspector UI goals remain valid: SeekTalent should consume this
package as a local dependency, read a bundled runtime snapshot, and receive
query recall optimization advice before calling CTS, Liepin, Boss, or other
providers. The missing product-quality layer is the centralized builder that
creates the graph snapshot from real JD corpora and historical retrieval
evidence.

## Current Problem

The current deterministic extractor is too narrow for real use. A small
hardcoded list of English technical terms cannot support broad JD corpora,
Chinese hiring language, cross-domain requirements, aliases, abbreviations,
equivalent terms, precision companions, or recall-risk decisions.

This is not an acceptable production foundation. Future work must remove the
hardcoded toy whitelist from the production path and replace it with a
data-driven graph construction pipeline.

## Product Objective

Build a complete offline pipeline that can:

- import a large real JD corpus into a clean build database from an explicit
  production corpus manifest;
- derive section-aware text windows with offsets and evidence snippets;
- extract keyword surfaces from real corpus evidence, historical query terms,
  curated taxonomies, provider recall data, and optional LLM candidate
  proposals;
- normalize and cluster surfaces into concepts;
- infer alias, abbreviation, equivalent, co-occurrence, precision companion,
  and query-risk relations with explicit provenance;
- store provider-aware recall observations for each surface and provider;
- evaluate extraction, clustering, relation inference, and recall optimization
  quality before snapshot release;
- prove completion on the already-available local 9000+ JD corpus, not only on
  fixtures or synthetic samples;
- build and validate a bundled runtime snapshot;
- keep runtime local, read-only, deterministic, and free of builder, CTS, LLM,
  network, and SeekTalent imports.

## GBrain Reference

Use `/Users/frankqdwang/MLE/gbrain-reference` as an architecture reference. Do
not delete it. Do not copy GBrain blindly. Translate its principles into this
domain:

- thin deterministic harness;
- product-owned rich skills and schema-owned domain knowledge;
- gazetteer/by-mention extraction;
- context-window relation inference;
- projection graph rebuild with provenance;
- optional offline LLM assistance with budget and review gates.

Rich skills and thin harness are product architecture for this builder. They are
not Codex development skills. LLM assistance is performed by this project's
offline builder through builder-only OpenAI-compatible provider configuration,
with Alibaba Cloud Bailian as the first intended provider.

## Non-Negotiable Quality Bar

This goal is not an MVP, demo, fixture exercise, or documentation-only plan.
The implementation must complete the real product path end to end. It must not
use placeholder data, fake success paths, fixture-specific branches, fixed
constant outputs, broad `except` swallowing, unused APIs, or hardcoded examples
that only pass tests.

If a behavior cannot be implemented honestly under the stated boundaries, stop,
document the blocker, and update readiness evidence instead of faking it.

Final completion criteria are defined in `06-completion-criteria.md`. That file
is part of the product requirement, not optional review guidance.

## CEO Review Findings To Bake In

Future execution must treat these as first-class product requirements, not
follow-up polish:

1. Production corpus manifest: the real JD corpus and historical query evidence
   need an explicit manifest with source IDs, paths, expected counts, content
   hash policy, privacy scan policy, language coverage, and build mode. A
   production build must start from this manifest and a clean build DB.
2. Graph quality eval gate: the builder must measure and report extraction
   coverage, false positives, alias/equivalent merge accuracy, bad merge risk,
   provider observation coverage, and query recall optimization behavior before
   release.
3. LLM candidate review gate: LLM output may propose candidates, but unreviewed
   or unvalidated LLM proposals must not enter the bundled runtime snapshot.
