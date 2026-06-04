# Supersession Map

`docs/superpowers/` has been intentionally removed from this repository. Do not
restore it and do not recreate Superpowers specs or linked implementation plans
to bypass the `04-gbrain-inspired-builder/` requirements.

This file records where the relevant historical acceptance context now lives.

## Current Sources Of Truth

- Product goal and package boundary: `GOAL.md`.
- GBrain-inspired builder target: `04-gbrain-inspired-builder/`.
- Query Recall Optimization contract: `docs/query-recall-optimization.md`.
- SeekTalent integration contract: `docs/seektalent-integration.md`.
- Query recall JSON contracts: `contracts/query-recall/`.
- Query plan JSON contracts: `contracts/query-plan/`.
- Release readiness evidence: `docs/readiness-report.md`.

## Historical Content Disposition

The deleted Superpowers files are not execution inputs. Their historical
material is superseded as follows:

- Runtime/builder split: kept in `GOAL.md`,
  `04-gbrain-inspired-builder/04-implementation-boundaries.md`, and
  `docs/seektalent-integration.md`.
- Provider-aware recall observations: kept in
  `docs/query-recall-optimization.md` and `contracts/query-recall/`.
- Snapshot packaging and bundled runtime requirements: kept in `GOAL.md`,
  `docs/release-checklist.md`, and `docs/readiness-report.md`.
- CTS safety boundary: kept in
  `04-gbrain-inspired-builder/04-implementation-boundaries.md`,
  `04-gbrain-inspired-builder/06-completion-criteria.md`, and
  `04-gbrain-inspired-builder/08-execution-contract.md`.
- Demo, fixture-only, help-only CLI, fixed-output, placeholder, or partial
  milestone behavior: explicitly discarded.

## Forbidden Regression

Future work must not:

- recreate `docs/superpowers/`;
- cite deleted Superpowers plans as approval to skip the `04` completion
  criteria;
- downgrade production completion to fixture, fake, mock, or dry-run evidence;
- treat the deleted plans as a reason to avoid the 9530-JD corpus build, clean
  DB rebuild, clean-context subagent reviews, or real CTS gate.
