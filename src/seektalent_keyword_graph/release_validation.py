"""Release validation for runtime snapshot artifacts."""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from seektalent_keyword_graph.contracts.snapshot import (
    SnapshotManifest,
    manifest_identity_sha256,
)
from seektalent_keyword_graph.runtime.errors import SnapshotError
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore


@dataclass(frozen=True)
class ReleaseValidationError:
    """Public validation error detail for release automation and tests."""

    code: str
    message: str


@dataclass(frozen=True)
class ReleaseValidationResult:
    """Typed release validation result."""

    artifact_path: Path
    manifest_path: Path
    compressed_snapshot_path: Path | None
    snapshot_size_bytes: int | None = None
    snapshot_sha256: str | None = None
    gzip_size_bytes: int | None = None
    gzip_sha256: str | None = None
    errors: tuple[ReleaseValidationError, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_release_artifacts(
    snapshot_path: str | Path,
    manifest_path: str | Path,
    *,
    compressed_snapshot_path: str | Path | None = None,
    max_gzip_bytes: int | None = None,
) -> ReleaseValidationResult:
    """Validate release artifact checksums, schema, privacy, and serving policy."""

    snapshot = Path(snapshot_path)
    manifest = Path(manifest_path)
    compressed = (
        Path(compressed_snapshot_path) if compressed_snapshot_path is not None else None
    )
    errors: list[ReleaseValidationError] = []

    snapshot_bytes = _read_artifact(snapshot, "snapshot", errors)
    manifest_payload = _read_manifest(manifest, errors)
    parsed_manifest = _parse_manifest(manifest_payload, errors)
    gzip_bytes = _read_artifact(compressed, "compressed_snapshot", errors)

    snapshot_sha256 = _sha256(snapshot_bytes)
    gzip_sha256 = _sha256(gzip_bytes)
    snapshot_size = len(snapshot_bytes) if snapshot_bytes is not None else None
    gzip_size = len(gzip_bytes) if gzip_bytes is not None else None

    if parsed_manifest is not None:
        _validate_manifest_artifact(
            parsed_manifest,
            "sqlite",
            snapshot,
            snapshot_size,
            snapshot_sha256,
            errors,
        )
        if compressed is not None:
            _validate_manifest_artifact(
                parsed_manifest,
                "sqlite_gzip",
                compressed,
                gzip_size,
                gzip_sha256,
                errors,
            )

    if (
        gzip_size is not None
        and max_gzip_bytes is not None
        and gzip_size > max_gzip_bytes
    ):
        errors.append(
            ReleaseValidationError(
                code="gzip_too_large",
                message=(
                    "compressed snapshot exceeds max size: "
                    f"{gzip_size} > {max_gzip_bytes}"
                ),
            )
        )

    if snapshot_bytes is not None and gzip_bytes is not None:
        try:
            decompressed = gzip.decompress(gzip_bytes)
        except OSError as exc:
            errors.append(
                ReleaseValidationError(
                    code="gzip_invalid",
                    message=f"compressed snapshot is not valid gzip: {exc}",
                )
            )
        else:
            if decompressed != snapshot_bytes:
                errors.append(
                    ReleaseValidationError(
                        code="gzip_payload_mismatch",
                        message=(
                            "compressed snapshot payload does not match snapshot bytes"
                        ),
                    )
                )

    store = _open_runtime_snapshot(snapshot, errors)
    if store is not None:
        try:
            if manifest_payload is not None:
                _validate_manifest_identity_meta(store, manifest_payload, errors)
            _validate_serving_surface_policy(store, errors)
        finally:
            store.close()

    return ReleaseValidationResult(
        artifact_path=snapshot,
        manifest_path=manifest,
        compressed_snapshot_path=compressed,
        snapshot_size_bytes=snapshot_size,
        snapshot_sha256=snapshot_sha256,
        gzip_size_bytes=gzip_size,
        gzip_sha256=gzip_sha256,
        errors=tuple(errors),
    )


def _read_artifact(
    path: Path | None, label: str, errors: list[ReleaseValidationError]
) -> bytes | None:
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError as exc:
        errors.append(
            ReleaseValidationError(
                code=f"{label}_read_error",
                message=f"{label} artifact is not readable: {path}: {exc}",
            )
        )
        return None


def _read_manifest(
    path: Path, errors: list[ReleaseValidationError]
) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(
            ReleaseValidationError(
                code="manifest_read_error",
                message=f"manifest is not readable: {path}: {exc}",
            )
        )
        return None
    except json.JSONDecodeError as exc:
        errors.append(
            ReleaseValidationError(
                code="manifest_json_error",
                message=f"manifest is not valid JSON: {exc}",
            )
        )
        return None
    if not isinstance(payload, dict):
        errors.append(
            ReleaseValidationError(
                code="manifest_shape_error",
                message="manifest must be a JSON object",
            )
        )
        return None
    return payload


def _parse_manifest(
    payload: dict[str, Any] | None, errors: list[ReleaseValidationError]
) -> SnapshotManifest | None:
    if payload is None:
        return None
    try:
        return SnapshotManifest.model_validate(payload)
    except ValidationError as exc:
        errors.append(
            ReleaseValidationError(
                code="manifest_contract_error",
                message=f"manifest contract validation failed: {exc}",
            )
        )
        return None


def _validate_manifest_artifact(
    manifest: SnapshotManifest,
    artifact_key: str,
    path: Path,
    actual_size: int | None,
    actual_sha256: str | None,
    errors: list[ReleaseValidationError],
) -> None:
    artifact_name = manifest.artifacts.get(artifact_key)
    if artifact_name is None:
        errors.append(
            ReleaseValidationError(
                code="manifest_missing_artifact",
                message=f"manifest missing artifact entry: {artifact_key}",
            )
        )
        return
    if Path(artifact_name).name != path.name:
        errors.append(
            ReleaseValidationError(
                code="manifest_artifact_path_mismatch",
                message=(
                    f"manifest artifact path mismatch for {artifact_key}: "
                    f"expected {artifact_name}, got {path.name}"
                ),
            )
        )
    expected_size = manifest.byte_sizes[artifact_key]
    if actual_size is not None and expected_size != actual_size:
        errors.append(
            ReleaseValidationError(
                code="manifest_size_mismatch",
                message=(
                    f"{artifact_key} byte size mismatch: "
                    f"expected {expected_size}, got {actual_size}"
                ),
            )
        )
    expected_sha256 = manifest.sha256[artifact_key]
    if actual_sha256 is not None and expected_sha256 != actual_sha256:
        errors.append(
            ReleaseValidationError(
                code="manifest_sha256_mismatch",
                message=(
                    f"{artifact_key} sha256 mismatch: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                ),
            )
        )


def _open_runtime_snapshot(
    snapshot_path: Path, errors: list[ReleaseValidationError]
) -> SQLiteSnapshotStore | None:
    try:
        return SQLiteSnapshotStore.open(snapshot_path)
    except SnapshotError as exc:
        errors.append(
            ReleaseValidationError(
                code=type(exc).__name__,
                message=str(exc),
            )
        )
        return None


def _validate_serving_surface_policy(
    store: SQLiteSnapshotStore, errors: list[ReleaseValidationError]
) -> None:
    try:
        store.validate()
    except SnapshotError as exc:
        errors.append(
            ReleaseValidationError(
                code="serving_surface_policy_error",
                message=str(exc),
            )
        )


def _validate_manifest_identity_meta(
    store: SQLiteSnapshotStore,
    manifest_payload: dict[str, Any],
    errors: list[ReleaseValidationError],
) -> None:
    meta = store.meta()
    expected = meta.get("manifest_sha256")
    actual = manifest_identity_sha256(manifest_payload)
    if expected != actual:
        errors.append(
            ReleaseValidationError(
                code="manifest_identity_sha256_mismatch",
                message=(
                    "manifest identity sha256 mismatch: "
                    f"expected {expected}, got {actual}"
                ),
            )
        )


def _sha256(data: bytes | None) -> str | None:
    if data is None:
        return None
    return hashlib.sha256(data).hexdigest()
