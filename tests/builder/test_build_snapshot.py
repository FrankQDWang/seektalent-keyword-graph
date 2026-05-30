from seektalent_keyword_graph.builder.build_snapshot import build_runtime_snapshot
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


def test_build_runtime_snapshot(tmp_path):
    output = tmp_path / "snapshot.sqlite3"
    build_runtime_snapshot(output)

    snapshot = SQLiteSnapshot.open(output)
    assert snapshot.meta()["kg_snapshot_id"].startswith("kg_")
    assert snapshot.meta()["snapshot_schema_version"] == "snapshot-v1"
