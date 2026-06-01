"""Builder-facing runtime snapshot validation API."""

from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.release_validation import (
    ReleaseValidationResult,
    validate_release_artifacts,
)


def validate_snapshot(
    snapshot_path: str | Path,
    manifest_path: str | Path,
    *,
    compressed_snapshot_path: str | Path | None = None,
    max_gzip_bytes: int | None = None,
) -> ReleaseValidationResult:
    """Validate a built runtime snapshot artifact set."""

    return validate_release_artifacts(
        snapshot_path,
        manifest_path,
        compressed_snapshot_path=compressed_snapshot_path,
        max_gzip_bytes=max_gzip_bytes,
    )
