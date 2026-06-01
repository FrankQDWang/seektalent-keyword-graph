# Release Checklist

This checklist gates a local runtime snapshot release. It does not authorize live
provider probes or SeekTalent main-project changes.

## Required Verification

Run these commands from the repository root before publishing artifacts:

```bash
uv sync --extra dev --extra builder
uv run pytest
uv run pytest tests/architecture -q
uv run pytest tests/integration/test_wheel_smoke.py -q
uv run pytest tests/integration/test_snapshot_artifact_validation.py -q
uv run ruff check .
uv run python -m build --wheel
uv run keyword-graph validate-snapshot --snapshot dist/snapshot.sqlite3 --manifest dist/snapshot-manifest.json --compressed-snapshot dist/snapshot.sqlite3.gz
```

Record each command, exit code, and first meaningful output line in
`docs/readiness-report.md`.

## Provider Gates

No real CTS call is allowed during unattended release verification. CTS, Liepin,
Boss, and future provider observations must already be present in the local
snapshot. Runtime validation must never read `KEYWORD_GRAPH_CTS_*`, import
builder/CTS modules, or perform network I/O.

Live provider probes belong to builder/probe workflows only. A real CTS probe
requires a separate human gate file with the exact approved token; fake and
dry-run modes are the default.

## Artifact Gates

Before publication, confirm the release bundle contains:

- SQLite runtime snapshot.
- `snapshot-manifest.json`.
- Gzip-compressed SQLite snapshot.
- Checksum and byte-size metadata matching every artifact.
- Provider-aware `provider_recall_observations` table and recall lookup indexes.
- No `cts_recall_observations` CTS-only replacement table.
- No candidate, resume, or secret markers.

## Publish Gate

Publishing is allowed only after validation passes and rollback ownership is
known. Keep the previous deployment pointer intact until the new snapshot has
been opened by the installed wheel smoke test.

## Rollback Gate

Keep the rollback runbook next to the release notes and rehearse the rollback
command sequence before changing the production deployment pointer.
