# SeekTalent Integration

This package is consumed as a runtime dependency by SeekTalent code. Do not modify the SeekTalent main project for this integration slice; keep the contract at the package boundary.

Runtime imports use only the public package API:

```python
from seektalent_keyword_graph import KeywordGraph
from seektalent_keyword_graph.config import KeywordGraphRuntimeSettings
from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryRecallRequest
```

The runtime side has no CTS credentials, no CTS client setup, and no runtime network I/O.
Provider totals are read from the local snapshot that was produced
offline by builder/release jobs.

## Environment

Only `SEEKTALENT_KEYWORD_GRAPH_*` variables are runtime settings:

| Variable | Meaning |
| --- | --- |
| `SEEKTALENT_KEYWORD_GRAPH_ENABLED` | Enable or bypass keyword graph usage. Defaults to `true`. |
| `SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH` | Local `.sqlite3` runtime snapshot path. |
| `SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID` | Optional expected snapshot id for deployment checks. |
| `SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN` | Return legacy behavior when graph loading fails. Defaults to `true`. |
| `SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES` | Default query-plan bundle cap. Defaults to `5`. |
| `SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER` | Provider used for query recall optimization when the caller has no provider context. Defaults to `cts`. |
| `SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES` | Default query recall alternative cap. Defaults to `5`. |

Runtime config must not read `KEYWORD_GRAPH_CTS_*`. Those variables belong only
to offline build/probe jobs.

## Fail Open

SeekTalent should treat package, artifact, or snapshot validation failures as
`keyword_graph_unavailable` and continue with the existing query path when
`SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN` is enabled.

```python
def open_keyword_graph_or_unavailable(snapshot_path, manifest_path=None):
    unavailable_errors = (ImportError, OSError)
    try:
        from seektalent_keyword_graph import KeywordGraph
        from seektalent_keyword_graph.runtime.errors import SnapshotError

        unavailable_errors = (*unavailable_errors, SnapshotError)
        return {
            "status": "ok",
            "graph": KeywordGraph.open(snapshot_path, manifest_path),
        }
    except ImportError as exc:
        return {
            "status": "keyword_graph_unavailable",
            "reason": type(exc).__name__,
        }
    except unavailable_errors as exc:
        return {
            "status": "keyword_graph_unavailable",
            "reason": type(exc).__name__,
        }
```

The effective unavailable exception set is `ImportError`, `OSError`, and
`SnapshotError`.

Missing package, missing snapshot, checksum mismatch, schema mismatch, or privacy
scan failure all use the same fail-open status. Consumers may log `reason`, but
must not expose raw artifact paths or stack traces to end users.

## Artifacts

SeekTalent receives a local runtime `.sqlite3` snapshot and manifest from release
automation. The runtime opens the snapshot read-only, validates schema,
checksum, privacy markers, provider metadata, and then serves deterministic
responses from local rows. It does not import builder modules or contact live
providers.
