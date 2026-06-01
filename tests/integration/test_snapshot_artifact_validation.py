from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from _fixture_flow_loader import load_run_fixture_flow

from seektalent_keyword_graph.release_validation import validate_release_artifacts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
run_fixture_flow = load_run_fixture_flow()


@dataclass(frozen=True)
class ArtifactCopy:
    snapshot_path: Path
    manifest_path: Path
    compressed_snapshot_path: Path


@pytest.fixture
def valid_artifacts(tmp_path: Path) -> ArtifactCopy:
    fixture = run_fixture_flow(tmp_path / "fixture")
    copy_dir = tmp_path / "copy"
    copy_dir.mkdir()
    snapshot = copy_dir / fixture.snapshot_path.name
    manifest = copy_dir / fixture.manifest_path.name
    source_compressed = Path(f"{fixture.snapshot_path}.gz")
    compressed = copy_dir / source_compressed.name
    shutil.copy2(fixture.snapshot_path, snapshot)
    shutil.copy2(fixture.manifest_path, manifest)
    shutil.copy2(source_compressed, compressed)
    return ArtifactCopy(snapshot, manifest, compressed)


@pytest.mark.parametrize(
    ("mutator_name", "expected"),
    [
        (
            "secret_marker",
            "keyword_graph_cts_",
        ),
        (
            "candidate_id_marker",
            "candidate_id",
        ),
        (
            "candidate_list_marker",
            "candidate_list",
        ),
        (
            "resume_marker",
            "resume_text",
        ),
        ("corrupt_snapshot_checksum", "sha256 mismatch"),
        ("drop_provider_observation_index", "required index"),
        ("replace_provider_table_with_cts_only_table", "provider_recall_observations"),
    ],
)
def test_release_validation_rejects_corrupt_snapshot_artifacts(
    valid_artifacts: ArtifactCopy,
    mutator_name: str,
    expected: str,
) -> None:
    mutators = _artifact_mutators()
    mutators[mutator_name](valid_artifacts)

    result = _validate(valid_artifacts)

    assert not result.ok
    assert any(expected in error.message.lower() for error in result.errors)


def test_release_validation_rejects_missing_manifest(
    valid_artifacts: ArtifactCopy,
) -> None:
    valid_artifacts.manifest_path.unlink()

    result = _validate(valid_artifacts)

    assert not result.ok
    assert {error.code for error in result.errors} >= {"manifest_read_error"}


def test_release_validation_rejects_oversized_compressed_artifact(
    valid_artifacts: ArtifactCopy,
) -> None:
    max_size = valid_artifacts.compressed_snapshot_path.stat().st_size - 1

    result = validate_release_artifacts(
        valid_artifacts.snapshot_path,
        valid_artifacts.manifest_path,
        compressed_snapshot_path=valid_artifacts.compressed_snapshot_path,
        max_gzip_bytes=max_size,
    )

    assert not result.ok
    assert any(error.code == "gzip_too_large" for error in result.errors)


def test_release_checklist_contains_required_release_gates() -> None:
    checklist = (PROJECT_ROOT / "docs" / "release-checklist.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "uv run pytest",
        "uv run ruff check",
        "uv run python -m build --wheel",
        "keyword-graph validate-snapshot",
        "No real CTS",
        "rollback",
    ):
        assert required in checklist


def test_rollback_runbook_contains_snapshot_restore_and_fail_open_steps() -> None:
    runbook = (PROJECT_ROOT / "docs" / "runbooks" / "rollback-snapshot.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "snapshot-manifest.json",
        "deployment pointer",
        "symlink",
        "restore previous snapshot",
        "fail-open",
        "keyword-graph validate-snapshot",
    ):
        assert required in runbook


def test_readiness_report_script_has_help() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/write_readiness_report.py", "--help"],
        check=True,
        capture_output=True,
        cwd=PROJECT_ROOT,
        text=True,
    )

    assert "release readiness report" in completed.stdout.lower()


def _validate(artifacts: ArtifactCopy):
    return validate_release_artifacts(
        artifacts.snapshot_path,
        artifacts.manifest_path,
        compressed_snapshot_path=artifacts.compressed_snapshot_path,
    )


def _artifact_mutators() -> dict[str, Callable[[ArtifactCopy], None]]:
    return {
        "secret_marker": lambda artifacts: _replace_surface_text(
            artifacts, "KEYWORD_GRAPH_CTS_TENANT_SECRET"
        ),
        "candidate_id_marker": lambda artifacts: _replace_surface_text(
            artifacts, "candidate_id"
        ),
        "candidate_list_marker": lambda artifacts: _replace_surface_text(
            artifacts, "candidate_list"
        ),
        "resume_marker": lambda artifacts: _replace_surface_text(
            artifacts, "resume_text"
        ),
        "corrupt_snapshot_checksum": _corrupt_snapshot_checksum,
        "drop_provider_observation_index": _drop_provider_observation_index,
        "replace_provider_table_with_cts_only_table": (
            _replace_provider_table_with_cts_only_table
        ),
    }


def _replace_surface_text(artifacts: ArtifactCopy, marker: str) -> None:
    conn = sqlite3.connect(artifacts.snapshot_path)
    try:
        conn.execute(
            "update surfaces set display_text = ? where surface_id = "
            "(select surface_id from surfaces order by surface_id limit 1)",
            (marker,),
        )
        conn.commit()
    finally:
        conn.close()


def _corrupt_snapshot_checksum(artifacts: ArtifactCopy) -> None:
    conn = sqlite3.connect(artifacts.snapshot_path)
    try:
        conn.execute(
            "update surfaces set ambiguity_score = ambiguity_score + 0.01 "
            "where surface_id = ("
            "select surface_id from surfaces order by surface_id limit 1"
            ")"
        )
        conn.commit()
    finally:
        conn.close()
    artifacts.compressed_snapshot_path.write_bytes(
        gzip.compress(artifacts.snapshot_path.read_bytes(), mtime=0)
    )
    _rewrite_manifest_gzip_only(artifacts)


def _drop_provider_observation_index(artifacts: ArtifactCopy) -> None:
    conn = sqlite3.connect(artifacts.snapshot_path)
    try:
        conn.execute("drop index idx_snapshot_provider_observations_surface_observed")
        conn.commit()
    finally:
        conn.close()


def _replace_provider_table_with_cts_only_table(artifacts: ArtifactCopy) -> None:
    conn = sqlite3.connect(artifacts.snapshot_path)
    try:
        conn.execute(
            "create table cts_recall_observations as "
            "select * from provider_recall_observations where provider = 'cts'"
        )
        conn.execute("drop table provider_recall_observations")
        conn.commit()
    finally:
        conn.close()


def _rewrite_manifest_gzip_only(artifacts: ArtifactCopy) -> None:
    payload = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    gzip_bytes = artifacts.compressed_snapshot_path.read_bytes()
    payload["byte_sizes"]["sqlite_gzip"] = len(gzip_bytes)
    payload["sha256"]["sqlite_gzip"] = hashlib.sha256(gzip_bytes).hexdigest()
    artifacts.manifest_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
