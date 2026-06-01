from __future__ import annotations

import pytest
from pydantic import ValidationError

from seektalent_keyword_graph.contracts import SnapshotManifest, SnapshotMeta


def _meta_payload() -> dict[str, object]:
    return {
        "kg_snapshot_id": "kg-snapshot-2026-05-31",
        "snapshot_schema_version": "snapshot-v1",
        "selection_policy_version": "policy-v1",
        "built_at": "2026-05-31T10:00:00Z",
        "source_corpus_version": "jd-corpus-2026-05-31",
        "builder_run_id": "builder-run-001",
        "build_report_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "provider_probe_window_start": "2026-05-31T09:00:00+08:00",
        "provider_probe_window_end": "2026-05-31T21:00:00+08:00",
        "provider_sources": ["liepin"],
        "created_by_package_version": "0.1.0",
    }


def _manifest_payload() -> dict[str, object]:
    return {
        "schema_version": "snapshot-v1",
        "kg_snapshot_id": "kg-snapshot-2026-05-31",
        "snapshot_schema_version": "snapshot-v1",
        "selection_policy_version": "policy-v1",
        "built_at": "2026-05-31T10:00:00Z",
        "source_corpus_version": "jd-corpus-2026-05-31",
        "builder_run_id": "builder-run-001",
        "artifacts": {
            "sqlite": "keyword-graph.sqlite3",
            "sqlite_gzip": "keyword-graph.sqlite3.gz",
        },
        "byte_sizes": {
            "sqlite": 1024,
            "sqlite_gzip": 512,
        },
        "sha256": {
            "sqlite": "c" * 64,
            "sqlite_gzip": "d" * 64,
        },
    }


def test_snapshot_meta_and_manifest_valid_payloads_validate() -> None:
    meta = SnapshotMeta.model_validate(_meta_payload())
    manifest = SnapshotManifest.model_validate(_manifest_payload())

    assert meta.snapshot_schema_version == "snapshot-v1"
    assert manifest.artifacts["sqlite"] == "keyword-graph.sqlite3"


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (SnapshotMeta, _meta_payload(), "kg_snapshot_id"),
        (SnapshotMeta, _meta_payload(), "manifest_sha256"),
        (SnapshotMeta, _meta_payload(), "provider_probe_window_start"),
        (SnapshotMeta, _meta_payload(), "provider_probe_window_end"),
        (SnapshotMeta, _meta_payload(), "provider_sources"),
        (SnapshotManifest, _manifest_payload(), "kg_snapshot_id"),
        (SnapshotManifest, _manifest_payload(), "artifacts"),
        (SnapshotManifest, _manifest_payload(), "byte_sizes"),
        (SnapshotManifest, _manifest_payload(), "sha256"),
    ],
)
def test_snapshot_required_public_fields_fail_when_removed(
    model: type, payload: dict[str, object], field: str
) -> None:
    payload_without_field = dict(payload)
    payload_without_field.pop(field)

    with pytest.raises(ValidationError):
        model.model_validate(payload_without_field)


@pytest.mark.parametrize(
    ("model", "payload"),
    [(SnapshotMeta, _meta_payload()), (SnapshotManifest, _manifest_payload())],
)
def test_snapshot_schema_and_policy_versions_reject_wrong_literals(
    model: type, payload: dict[str, object]
) -> None:
    wrong_schema = dict(payload)
    wrong_schema["snapshot_schema_version"] = "snapshot-v2"
    with pytest.raises(ValidationError):
        model.model_validate(wrong_schema)

    wrong_policy = dict(payload)
    wrong_policy["selection_policy_version"] = "policy-v2"
    with pytest.raises(ValidationError):
        model.model_validate(wrong_policy)


@pytest.mark.parametrize(
    ("model", "payload"),
    [(SnapshotMeta, _meta_payload()), (SnapshotManifest, _manifest_payload())],
)
def test_snapshot_contracts_reject_extra_fields(
    model: type, payload: dict[str, object]
) -> None:
    payload_with_extra = dict(payload)
    payload_with_extra["unexpected"] = "value"

    with pytest.raises(ValidationError):
        model.model_validate(payload_with_extra)


def test_snapshot_meta_accepts_legacy_cts_probe_window_optional() -> None:
    payload = _meta_payload()
    payload["cts_probe_window_start"] = "2026-05-31T09:00:00+08:00"
    payload["cts_probe_window_end"] = "2026-05-31T21:00:00+08:00"

    meta = SnapshotMeta.model_validate(payload)

    assert meta.provider_probe_window_start == "2026-05-31T09:00:00+08:00"
    assert meta.provider_sources == ["liepin"]


def test_snapshot_manifest_rejects_negative_byte_sizes() -> None:
    payload = _manifest_payload()
    payload["byte_sizes"] = {"sqlite": -1, "sqlite_gzip": 512}

    with pytest.raises(ValidationError):
        SnapshotManifest.model_validate(payload)


@pytest.mark.parametrize("bad_hash", ["abc", "g" * 64, "c" * 63, "c" * 65])
def test_snapshot_manifest_rejects_non_64_hex_sha256_values(bad_hash: str) -> None:
    payload = _manifest_payload()
    payload["sha256"] = {"sqlite": bad_hash, "sqlite_gzip": "d" * 64}

    with pytest.raises(ValidationError):
        SnapshotManifest.model_validate(payload)


@pytest.mark.parametrize(
    "artifacts",
    [
        {},
        {"": "keyword-graph.sqlite3"},
        {"sqlite": ""},
        {"sqlite": "keyword-graph.sqlite3", "sqlite_gzip": "   "},
    ],
)
def test_snapshot_manifest_rejects_empty_artifact_metadata(
    artifacts: dict[str, str]
) -> None:
    payload = _manifest_payload()
    payload["artifacts"] = artifacts

    with pytest.raises(ValidationError):
        SnapshotManifest.model_validate(payload)


@pytest.mark.parametrize(
    ("byte_sizes", "sha256"),
    [
        ({"sqlite": 1024}, {"sqlite": "c" * 64, "sqlite_gzip": "d" * 64}),
        ({"sqlite": 1024, "sqlite_gzip": 512}, {"sqlite": "c" * 64}),
    ],
)
def test_snapshot_manifest_requires_matching_artifact_key_sets(
    byte_sizes: dict[str, int], sha256: dict[str, str]
) -> None:
    payload = _manifest_payload()
    payload["byte_sizes"] = byte_sizes
    payload["sha256"] = sha256

    with pytest.raises(ValidationError):
        SnapshotManifest.model_validate(payload)
