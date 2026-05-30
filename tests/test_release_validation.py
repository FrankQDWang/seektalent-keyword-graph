from seektalent_keyword_graph.release_validation import (
    calculate_sha256,
    validate_snapshot_artifact,
    validate_snapshot_size,
    write_manifest,
)


def test_validate_snapshot_size_allows_small_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"small")

    assert validate_snapshot_size(path, max_bytes=100)


def test_validate_snapshot_size_rejects_large_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"large")

    assert not validate_snapshot_size(path, max_bytes=3)


def test_manifest_checksum_roundtrip(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"snapshot-bytes")

    write_manifest(snapshot, manifest)

    assert validate_snapshot_artifact(snapshot, manifest, max_bytes=100)
    assert calculate_sha256(snapshot) == calculate_sha256(snapshot)


def test_manifest_checksum_rejects_changed_file(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"snapshot-bytes")
    write_manifest(snapshot, manifest)
    snapshot.write_bytes(b"changed")

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)


def test_validate_snapshot_artifact_rejects_secret_marker(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"KEYWORD_GRAPH_CTS_TENANT_SECRET=secret")
    write_manifest(snapshot, manifest)

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)


def test_validate_snapshot_artifact_rejects_candidate_or_resume_markers(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"candidate_list=[alice]; resume_text=private")
    write_manifest(snapshot, manifest)

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)
