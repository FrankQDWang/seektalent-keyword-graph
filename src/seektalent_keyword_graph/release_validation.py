from __future__ import annotations

import hashlib
import json
from pathlib import Path

FORBIDDEN_MARKERS = (
    b"KEYWORD_GRAPH_CTS_",
    b"tenant_secret",
    b"candidate_id",
    b"candidate_list",
    b"resume_text",
)


def validate_snapshot_size(path: Path, max_bytes: int = 100 * 1024 * 1024) -> bool:
    return path.exists() and path.stat().st_size <= max_bytes


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(snapshot_path: Path, manifest_path: Path) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "artifact": snapshot_path.name,
                "bytes": snapshot_path.stat().st_size,
                "sha256": calculate_sha256(snapshot_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def manifest_matches(snapshot_path: Path, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text())
    return (
        manifest.get("artifact") == snapshot_path.name
        and manifest.get("bytes") == snapshot_path.stat().st_size
        and manifest.get("sha256") == calculate_sha256(snapshot_path)
    )


def scan_forbidden_markers(path: Path) -> list[str]:
    payload = path.read_bytes().lower()
    return [marker.decode() for marker in FORBIDDEN_MARKERS if marker.lower() in payload]


def validate_snapshot_artifact(
    snapshot_path: Path,
    manifest_path: Path,
    max_bytes: int = 100 * 1024 * 1024,
) -> bool:
    return (
        validate_snapshot_size(snapshot_path, max_bytes)
        and manifest_matches(snapshot_path, manifest_path)
        and not scan_forbidden_markers(snapshot_path)
    )
