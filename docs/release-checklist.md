# Release Checklist

- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run python -m build --wheel` passes.
- [ ] Snapshot validates.
- [ ] Compressed snapshot is below 100MB.
- [ ] Snapshot contains no CTS key.
- [ ] Snapshot contains no candidate list or resume text.
- [ ] Manifest and checksum are generated.
- [ ] CLI `--help` lists every promised builder command.
- [ ] `keyword-graph probe-cts --dry-run Python` prints payload only and makes no CTS call.
- [ ] Rollback path points to previous snapshot.
