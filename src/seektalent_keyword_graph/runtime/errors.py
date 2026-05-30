class KeywordGraphError(Exception):
    """Base error for seektalent-keyword-graph."""


class SnapshotUnavailableError(KeywordGraphError):
    """Snapshot file cannot be opened."""


class UnsupportedSnapshotError(KeywordGraphError):
    """Snapshot schema is not supported."""


class SnapshotIntegrityError(KeywordGraphError):
    """Snapshot exists but required data is missing or corrupt."""
