"""Runtime snapshot access and typed errors."""

from seektalent_keyword_graph.runtime.errors import (
    KeywordGraphRuntimeError,
    SnapshotChecksumError,
    SnapshotError,
    SnapshotFormatError,
    SnapshotPrivacyError,
    SnapshotSchemaError,
    UnsupportedSnapshotVersionError,
)
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore

__all__ = [
    "KeywordGraphRuntimeError",
    "SQLiteSnapshotStore",
    "SnapshotChecksumError",
    "SnapshotError",
    "SnapshotFormatError",
    "SnapshotPrivacyError",
    "SnapshotSchemaError",
    "UnsupportedSnapshotVersionError",
]
