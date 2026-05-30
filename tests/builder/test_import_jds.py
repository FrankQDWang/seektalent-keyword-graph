from pathlib import Path

from seektalent_keyword_graph.builder.import_jds import import_jds


def test_import_jds(tmp_path):
    db_path = tmp_path / "build.sqlite3"
    count = import_jds(Path("tests/fixtures/jds/sample_jds.jsonl"), db_path)

    assert count == 2
