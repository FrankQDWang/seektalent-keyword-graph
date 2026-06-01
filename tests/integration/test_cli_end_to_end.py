from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from seektalent_keyword_graph import cli

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
JD_FIXTURE = FIXTURES / "jds" / "full_flow_jds.jsonl"
CTS_FIXTURE = FIXTURES / "cts" / "fake_totals.json"


def run_json(args: list[str], capsys) -> dict[str, object]:
    code = cli.main(args)
    captured = capsys.readouterr()
    assert code == 0, captured.err
    return json.loads(captured.out)


def test_cli_contract_minimal_commands_build_and_validate_snapshot(
    tmp_path: Path, capsys
) -> None:
    build_db = tmp_path / "build.sqlite3"
    out_dir = tmp_path / "out"

    import_payload = run_json(
        [
            "import-jds",
            str(JD_FIXTURE),
            "--build-db",
            str(build_db),
            "--corpus-version",
            "fixture-v1",
        ],
        capsys,
    )
    assert import_payload["status"] == "ok"

    run_json(
        [
            "extract-surfaces",
            "--build-db",
            str(build_db),
            "--report",
            str(out_dir / "extraction-report.json"),
        ],
        capsys,
    )
    run_json(
        [
            "build-relations",
            "--build-db",
            str(build_db),
            "--sampling-csv",
            str(out_dir / "sampling.csv"),
            "--sampling-jsonl",
            str(out_dir / "sampling.jsonl"),
        ],
        capsys,
    )
    run_json(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--fake-response",
            str(CTS_FIXTURE),
            "--dry-run",
        ],
        capsys,
    )
    snapshot_payload = run_json(
        [
            "build-snapshot",
            "--build-db",
            str(build_db),
            "--snapshot",
            str(out_dir / "kg.sqlite3"),
            "--manifest",
            str(out_dir / "kg.manifest.json"),
        ],
        capsys,
    )
    paths = snapshot_payload["paths"]
    snapshot = Path(paths["snapshot"])
    manifest = Path(paths["manifest"])
    compressed = Path(paths["compressed_snapshot"])
    assert snapshot.name == "kg.sqlite3"
    assert manifest.name == "kg.manifest.json"
    assert compressed.name == "kg.sqlite3.gz"
    assert compressed.is_file()

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["builder_run_id"] == "local-cli-run"
    assert manifest_payload["source_corpus_version"] == "fixture-v1"
    assert manifest_payload["artifacts"]["sqlite"] == snapshot.name
    assert manifest_payload["artifacts"]["sqlite_gzip"] == compressed.name

    validation_payload = run_json(
        [
            "validate-snapshot",
            "--snapshot",
            str(snapshot),
            "--manifest",
            str(manifest),
        ],
        capsys,
    )
    assert validation_payload["ok"] is True


def test_cli_end_to_end_builds_and_validates_snapshot(tmp_path: Path, capsys) -> None:
    build_db = tmp_path / "build.sqlite3"
    out_dir = tmp_path / "out"
    run_id = "run-e2e"

    run_json(
        [
            "import-jds",
            str(JD_FIXTURE),
            "--build-db",
            str(build_db),
            "--builder-run-id",
            run_id,
            "--corpus-version",
            "fixture-v1",
        ],
        capsys,
    )
    run_json(
        [
            "extract-surfaces",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            run_id,
            "--report",
            str(out_dir / "extraction-report.json"),
        ],
        capsys,
    )
    run_json(
        [
            "build-relations",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            run_id,
            "--sampling-csv",
            str(out_dir / "sampling.csv"),
            "--sampling-jsonl",
            str(out_dir / "sampling.jsonl"),
        ],
        capsys,
    )
    run_json(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            run_id,
            "--dry-run",
            "--fake-response",
            str(CTS_FIXTURE),
        ],
        capsys,
    )

    snapshot_payload = run_json(
        [
            "build-snapshot",
            "--build-db",
            str(build_db),
            "--snapshot",
            str(out_dir / "kg.sqlite3"),
            "--manifest",
            str(out_dir / "kg.manifest.json"),
            "--kg-snapshot-id",
            "kg-e2e",
            "--source-corpus-version",
            "fixture-v1",
            "--builder-run-id",
            run_id,
            "--provider-probe-window-start",
            "2026-05-31T00:00:00Z",
            "--provider-probe-window-end",
            "2026-06-01T00:00:00Z",
        ],
        capsys,
    )

    assert snapshot_payload["command"] == "build-snapshot"
    assert snapshot_payload["status"] == "ok"
    paths = snapshot_payload["paths"]
    snapshot = Path(paths["snapshot"])
    manifest = Path(paths["manifest"])
    compressed = Path(paths["compressed_snapshot"])
    build_report = Path(paths["build_report"])
    assert snapshot.is_file()
    assert manifest.is_file()
    assert compressed.is_file()
    assert build_report.is_file()
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["artifacts"]["sqlite"] == snapshot.name
    assert manifest_payload["artifacts"]["sqlite_gzip"] == compressed.name

    validation_payload = run_json(
        [
            "validate-snapshot",
            "--snapshot",
            str(snapshot),
            "--manifest",
            str(manifest),
            "--compressed-snapshot",
            str(compressed),
        ],
        capsys,
    )
    assert validation_payload["status"] == "ok"
    assert validation_payload["ok"] is True

    manifest.write_text('{"broken": true}', encoding="utf-8")
    code = cli.main(
        [
            "validate-snapshot",
            "--snapshot",
            str(snapshot),
            "--manifest",
            str(manifest),
            "--compressed-snapshot",
            str(compressed),
        ]
    )
    captured = capsys.readouterr()
    assert code != 0
    invalid_payload = json.loads(captured.out)
    assert invalid_payload["status"] == "error"
    assert invalid_payload["ok"] is False
    assert invalid_payload["errors"]


def test_probe_cts_real_bad_gate_content_must_match_exact_token(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    build_db = tmp_path / "build.sqlite3"
    bad_gate = tmp_path / "bad.txt"
    bad_gate.write_text("REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH extra\n", encoding="utf-8")

    def fail_real_client(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("real CTS client must not be constructed")

    monkeypatch.setattr(
        "seektalent_keyword_graph.cts.count_client.CtsCountClient",
        fail_real_client,
    )

    code = cli.main(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-e2e",
            "--real",
            "--gate-file",
            str(bad_gate),
        ]
    )
    captured = capsys.readouterr()

    assert code != 0
    assert "invalid CTS real-mode gate token" in captured.err

    bad_gate.write_text(
        "REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH\nextra\n", encoding="utf-8"
    )
    code = cli.main(
        [
            "probe-cts",
            "--build-db",
            str(build_db),
            "--builder-run-id",
            "run-e2e",
            "--real",
            "--gate-file",
            str(bad_gate),
        ]
    )
    captured = capsys.readouterr()

    assert code != 0
    assert "invalid CTS real-mode gate token" in captured.err

    connection = sqlite3.connect(build_db)
    try:
        jobs = connection.execute("select count(*) from probe_jobs").fetchone()[0]
    finally:
        connection.close()
    assert jobs == 0
