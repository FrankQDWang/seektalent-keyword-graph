"""Typed runtime and snapshot errors."""

from __future__ import annotations


class KeywordGraphRuntimeError(Exception):
    """Base class for keyword graph runtime failures."""


class SnapshotError(KeywordGraphRuntimeError):
    """Base class for snapshot open and validation failures."""


class SnapshotFormatError(SnapshotError):
    """Raised when a snapshot is missing, unreadable, or not valid SQLite."""


class SnapshotSchemaError(SnapshotError):
    """Raised when required snapshot tables, indexes, or metadata are invalid."""


class UnsupportedSnapshotVersionError(SnapshotSchemaError):
    """Raised when the snapshot schema version is not supported."""


class SnapshotChecksumError(SnapshotError):
    """Raised when a provided manifest does not match the snapshot artifact."""


class SnapshotPrivacyError(SnapshotError):
    """Raised when a snapshot contains forbidden private markers."""
