# Snapshot Rollback Runbook

Use this runbook when a published keyword graph runtime snapshot must be
withdrawn without changing the SeekTalent main project.

## Inputs

- Previous SQLite snapshot path.
- Previous `snapshot-manifest.json`.
- Previous gzip snapshot path.
- Current deployment pointer, usually a symlink or small config file read by
  the consumer service.

## Preflight

Validate the previous artifacts before changing any pointer:

```bash
uv run keyword-graph validate-snapshot --snapshot /path/to/previous/snapshot.sqlite3 --manifest /path/to/previous/snapshot-manifest.json --compressed-snapshot /path/to/previous/snapshot.sqlite3.gz
```

Confirm the command exits 0 and that the manifest checksum matches the snapshot
bytes.

## Rollback

1. Stop publication of the bad artifact bundle.
2. Move the deployment pointer back to the previous manifest and snapshot
   bundle. If the pointer is a symlink, replace it atomically with a symlink to
   the previous release directory.
3. restore previous snapshot ownership and permissions exactly as recorded for
   the prior release.
4. Restart or reload only the consumer process that reads the pointer.
5. Open the previous snapshot through the runtime package and verify the
   expected snapshot id.

## Fail Open

If rollback validation fails, leave SeekTalent in fail-open mode: keep the
original `RequirementSheet.initial_query_term_pool` /
`RetrievalState.query_term_pool` unchanged and skip keyword graph optimization
until a valid snapshot is restored.

## Post-Rollback Checks

Run:

```bash
uv run keyword-graph validate-snapshot --snapshot /path/to/current/snapshot.sqlite3 --manifest /path/to/current/snapshot-manifest.json --compressed-snapshot /path/to/current/snapshot.sqlite3.gz
```

Record the deployment pointer target, symlink target when applicable, command
exit code, and operator in the release log.
