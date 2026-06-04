"""Locate the runtime snapshot shipped inside the installed package."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from seektalent_keyword_graph.config import KeywordGraphRuntimeSettings
from seektalent_keyword_graph.runtime.errors import SnapshotFormatError

BUNDLED_SNAPSHOT_PACKAGE = "seektalent_keyword_graph.data"
BUNDLED_SNAPSHOT_FILENAME = "keyword-graph.sqlite3"
BUNDLED_MANIFEST_FILENAME = "snapshot-manifest.json"


@dataclass(frozen=True)
class SnapshotLocation:
    snapshot_path: Path
    manifest_path: Path | None
    source: Literal["override", "bundled"]


def resolve_snapshot_location(
    settings: KeywordGraphRuntimeSettings,
) -> SnapshotLocation:
    if settings.snapshot_path is not None:
        return SnapshotLocation(
            snapshot_path=settings.snapshot_path,
            manifest_path=settings.manifest_path,
            source="override",
        )
    if settings.manifest_path is not None:
        raise SnapshotFormatError(
            "SEEKTALENT_KEYWORD_GRAPH_MANIFEST_PATH requires "
            "SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH"
        )
    if settings.mode == "dev":
        raise SnapshotFormatError(
            "dev mode requires SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH"
        )
    return _bundled_snapshot_location()


def _bundled_snapshot_location() -> SnapshotLocation:
    try:
        package_root = resources.files(BUNDLED_SNAPSHOT_PACKAGE)
    except ModuleNotFoundError as exc:
        raise SnapshotFormatError(
            "bundled runtime snapshot package is not available"
        ) from exc

    snapshot_resource = package_root.joinpath(BUNDLED_SNAPSHOT_FILENAME)
    if not snapshot_resource.is_file():
        raise SnapshotFormatError(
            "bundled runtime snapshot is not packaged: "
            f"{BUNDLED_SNAPSHOT_PACKAGE}/{BUNDLED_SNAPSHOT_FILENAME}"
        )

    manifest_resource = package_root.joinpath(BUNDLED_MANIFEST_FILENAME)
    manifest_path = (
        _resource_path(manifest_resource) if manifest_resource.is_file() else None
    )
    return SnapshotLocation(
        snapshot_path=_resource_path(snapshot_resource),
        manifest_path=manifest_path,
        source="bundled",
    )


def _resource_path(resource: resources.abc.Traversable) -> Path:
    if isinstance(resource, Path):
        return resource
    path = Path(str(resource))
    if path.is_file():
        return path
    raise SnapshotFormatError(
        "bundled runtime snapshot must be installed as filesystem package data"
    )
