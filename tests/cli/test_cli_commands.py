from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from seektalent_keyword_graph import cli

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
JD_FIXTURE = FIXTURES / "jds" / "full_flow_jds.jsonl"
CTS_FIXTURE = FIXTURES / "cts" / "fake_totals.json"


def run_cli(args: list[str], capsys) -> tuple[int, str, str]:
    code = cli.main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def json_stdout(args: list[str], capsys) -> dict[str, object]:
    code, out, err = run_cli(args, capsys)
    assert code == 0, err
    return json.loads(out)


def count_rows(db_path: Path, table: str) -> int:
    connection = sqlite3.connect(db_path)
    try:
        return int(connection.execute(f"select count(*) from {table}").fetchone()[0])
    finally:
        connection.close()


def seed_extracted_build_db(tmp_path: Path, capsys) -> Path:
    build_db = tmp_path / "build.sqlite3"
    json_stdout(
        [
            "import-jds",
            str(JD_FIXTURE),
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--corpus-version",
            "fixture-v1",
        ],
        capsys,
    )
    json_stdout(
        [
            "extract-surfaces",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--report",
            str(tmp_path / "extraction-report.json"),
        ],
        capsys,
    )
    return build_db


def test_all_promised_commands_have_help_output(capsys) -> None:
    commands = (
        "import-jds",
        "extract-surfaces",
        "build-relations",
        "probe-cts",
        "build-snapshot",
        "validate-snapshot",
    )

    for command in commands:
        code, out, err = run_cli([command, "--help"], capsys)

        assert code == 0, err
        assert f"usage: keyword-graph {command}" in out


def test_import_jds_creates_build_db_from_fixture_jsonl(tmp_path: Path, capsys) -> None:
    build_db = tmp_path / "build.sqlite3"

    payload = json_stdout(
        [
            "import-jds",
            str(JD_FIXTURE),
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--corpus-version",
            "fixture-v1",
        ],
        capsys,
    )

    assert payload["command"] == "import-jds"
    assert payload["status"] == "ok"
    assert payload["report"]["imported_count"] == 2
    assert payload["report"]["duplicate_count"] == 1
    assert payload["report"]["error_count"] == 3
    assert build_db.is_file()
    assert count_rows(build_db, "jd_documents") == 2


def test_extract_surfaces_updates_build_db_and_writes_report(
    tmp_path: Path, capsys
) -> None:
    build_db = seed_extracted_build_db(tmp_path, capsys)
    report_path = tmp_path / "extraction-report.json"

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["command"] == "extract-surfaces"
    assert payload["status"] == "ok"
    assert payload["report"]["jd_count"] == 2
    assert payload["report"]["surface_count"] > 0
    assert count_rows(build_db, "surfaces") == payload["report"]["surface_count"]
    assert count_rows(build_db, "keyword_mentions") == payload["report"][
        "mention_count"
    ]


def test_build_relations_updates_tables_and_writes_sampling_reports(
    tmp_path: Path, capsys
) -> None:
    build_db = seed_extracted_build_db(tmp_path, capsys)
    sampling_csv = tmp_path / "out" / "sampling.csv"
    sampling_jsonl = tmp_path / "out" / "sampling.jsonl"

    payload = json_stdout(
        [
            "build-relations",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--sampling-csv",
            str(sampling_csv),
            "--sampling-jsonl",
            str(sampling_jsonl),
        ],
        capsys,
    )

    assert payload["command"] == "build-relations"
    assert payload["status"] == "ok"
    assert payload["relations"]["concept_count"] == count_rows(build_db, "concepts")
    assert payload["relations"]["relation_count"] == count_rows(
        build_db, "surface_relations"
    )
    assert payload["cooccurrence"]["edge_count"] == count_rows(
        build_db, "cooccurrence_edges"
    )
    assert sampling_csv.read_text(encoding="utf-8").startswith(
        "target_type,target_id,display_text"
    )
    assert sampling_jsonl.is_file()


def test_probe_cts_dry_run_fake_response_writes_cts_observations_without_real_call(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    build_db = seed_extracted_build_db(tmp_path, capsys)
    json_stdout(
        [
            "build-relations",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--sampling-csv",
            str(tmp_path / "sampling.csv"),
            "--sampling-jsonl",
            str(tmp_path / "sampling.jsonl"),
        ],
        capsys,
    )

    def fail_real_client(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("real CTS client must not be constructed")

    monkeypatch.setattr(
        "seektalent_keyword_graph.cts.count_client.CtsCountClient",
        fail_real_client,
    )

    payload = json_stdout(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--dry-run",
            "--fake-response",
            str(CTS_FIXTURE),
        ],
        capsys,
    )

    assert payload["command"] == "probe-cts"
    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert payload["summary"]["scheduled"] > 0
    assert payload["summary"]["completed"] == payload["summary"]["scheduled"]

    connection = sqlite3.connect(build_db)
    try:
        rows = connection.execute(
            "select distinct provider, provider_api_version, status "
            "from provider_recall_observations"
        ).fetchall()
    finally:
        connection.close()
    assert rows == [("cts", "dry-run-v1", "ok")]


def test_invalid_arguments_return_nonzero_with_actionable_stderr(capsys) -> None:
    code, _out, err = run_cli(["import-jds", "--build-db", "build.sqlite3"], capsys)

    assert code != 0
    assert "the following arguments are required: INPUT_JSONL" in err


def test_probe_cts_real_fails_closed_without_valid_gate(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    build_db = tmp_path / "build.sqlite3"
    bad_gate = tmp_path / "bad.txt"
    bad_gate.write_text("not allowed\n", encoding="utf-8")

    def fail_real_client(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("real CTS client must not be constructed")

    monkeypatch.setattr(
        "seektalent_keyword_graph.cts.count_client.CtsCountClient",
        fail_real_client,
    )

    code, _out, err = run_cli(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--real",
        ],
        capsys,
    )
    assert code != 0
    assert "real CTS probe mode requires a gate file" in err

    code, _out, err = run_cli(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-cli",
            "--real",
            "--gate-file",
            str(bad_gate),
        ],
        capsys,
    )
    assert code != 0
    assert "invalid CTS real-mode gate token" in err
