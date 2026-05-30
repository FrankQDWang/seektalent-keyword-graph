## Agent Workflow Routing

Use the curated `fw-*` workflow as the default interface for gstack + Superpowers:

- `fw-office-hours`: idea intake, demand reality, and product direction.
- `fw-ceo-review`: CEO-level scope, ambition, and premise review.
- `fw-plan`: Superpowers spec + linked implementation plan.
- `fw-plan-review`: gstack plan engineering review, with conditional design review.
- `fw-build`: implementation discipline.
- `fw-debug`: root-cause debugging.
- `fw-review`: Superpowers review discipline plus raw gstack review gate.
- `fw-ship-lite`: branch finish and release-readiness report only.

Ownership:

- gstack owns direction, scope, architecture challenge, planning gates, review, QA, and release gates.
- Superpowers owns implementation discipline: specs, plans, TDD, debugging, and verification.
- Codex owns runtime execution, local tools, memory, and approved parallel agent orchestration.

Rules:

- One task has one execution owner.
- Prefer the `fw-*` wrapper skills over raw gstack or raw Superpowers skills.
- Raw gstack and raw Superpowers content is upstream reference material unless a wrapper explicitly includes it.
- Do not use standalone/native Codex review as the review owner.
- Repo files are source of truth; Codex memory is supporting context, not canonical project documentation.

## Stage Gates

- `fw-office-hours` runs `office-hours` only, then stops before `fw-ceo-review`.
- `fw-ceo-review` runs `plan-ceo-review` only, then stops before `fw-plan`.
- `fw-plan` uses Superpowers `writing-plans` to write or update the spec plus linked plan. It does not run gstack planning review.
- `fw-plan-review` runs `plan-eng-review`; use `plan-design-review` only when UI/UX is affected. Stop before `fw-build`.
- `fw-build` executes only an approved plan that links back to its spec.
- `fw-review` uses the curated Superpowers + raw gstack review chain, not generic Codex review.
- `fw-ship-lite` reports readiness only. Push, PR, merge, deploy, release, and canary require a separate explicit gate.

## Skill Loading Discipline

- Installed skills are callable surfaces, not active project truth.
- Do not load raw upstream skill bodies unless the user explicitly invokes them or the active `fw-*` wrapper requires them.
- Prefer explicit user-invoked skills over automatic skill selection when multiple workflows match.

## General Coding Discipline

These are default behavioral preferences. They yield to system/developer instructions, explicit user requests, repository AGENTS.md, and active workflow skills such as `fw-*`.

### Think Before Coding

For non-trivial changes, state the working assumption and success criteria before editing.

If ambiguity materially changes behavior, API shape, data safety, or implementation scope, ask before coding. If the ambiguity is low-risk, make a reasonable assumption, state it briefly, and proceed.

Surface important tradeoffs when they affect maintainability, correctness, or product behavior.

### Simplicity First

Implement the minimum code that fully solves the requested problem.

Do not add speculative features, generic extension points, broad configuration, fallback chains, or abstractions for single-use code.

Prefer direct, readable code over clever compression. If the implementation becomes larger or more indirect than the problem warrants, simplify before finalizing.

### Surgical Changes

Touch only files and lines needed for the request.

Do not refactor adjacent code, reformat unrelated sections, or clean up pre-existing dead code unless asked.

Remove only unused imports, variables, functions, or tests introduced by your own changes.

Every changed line should have a clear relationship to the task.

### Goal-Driven Execution

For bugs, prefer reproducing the issue with a focused test or command before fixing it.

For behavior changes, define what passing verification means before implementation.

For refactors, preserve behavior and run the relevant tests before and after when practical.

For multi-step non-trivial work, use a short checklist with verification for each step.
