from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "write_readiness_report.py"


def test_readiness_report_renders_required_evidence_with_injected_runner(
    tmp_path: Path,
) -> None:
    module = _load_writer()
    calls: list[str] = []
    work_dir = tmp_path / "readiness-fixture-flow"
    snapshot = work_dir / "snapshot" / "kg.sqlite3"
    manifest = work_dir / "snapshot" / "kg.manifest.json"
    compressed = Path(f"{snapshot}.gz")

    def fake_runner(command: str, cwd: Path) -> object:
        assert cwd == PROJECT_ROOT
        calls.append(command)
        if command == module.OLD_NAME_SCAN_COMMAND:
            return module.CommandResult(
                command=command,
                exit_code=1,
                stdout="",
                stderr="",
            )
        if command == module.fixture_flow_command(work_dir):
            return module.CommandResult(
                command=command,
                exit_code=0,
                stdout=(
                    "{\n"
                    f'  "snapshot_path": "{snapshot}",\n'
                    f'  "manifest_path": "{manifest}",\n'
                    '  "summary": {"query_recall_actions": 4}\n'
                    "}\n"
                ),
                stderr="",
            )
        if command == module.validation_command(snapshot, manifest, compressed):
            return module.CommandResult(
                command=command,
                exit_code=0,
                stdout="snapshot validation passed\n",
                stderr="",
            )
        return module.CommandResult(
            command=command,
            exit_code=0,
            stdout=f"{command} completed\n",
            stderr="",
        )

    output = tmp_path / "readiness-report.md"
    report = module.generate_report(
        output_path=output,
        runner=fake_runner,
        root=PROJECT_ROOT,
        work_dir=work_dir,
        head_provider=lambda: "abc123head",
    )

    assert report.ok
    assert output.read_text(encoding="utf-8") == report.markdown
    assert calls == [
        *module.FINAL_VERIFICATION_COMMANDS,
        module.fixture_flow_command(work_dir),
        module.validation_command(snapshot, manifest, compressed),
    ]
    assert "HEAD: `abc123head`" in report.markdown
    rendered_old_name_scan = module.render_command_for_report(
        module.OLD_NAME_SCAN_COMMAND
    )
    assert f"- Command: `{rendered_old_name_scan}`" in report.markdown
    assert "  Exit code: 1" in report.markdown
    assert "  Status: success/no matches" in report.markdown
    assert "  First meaningful output line: (no output)" in report.markdown

    for milestone, items in module.ACCEPTANCE_EVIDENCE.items():
        assert f"### {milestone}" in report.markdown
        for item in items:
            assert item.acceptance in report.markdown
            assert item.evidence in report.markdown
            assert item.status

    for heading in (
        "## Query Recall Optimization Status",
        "## Provider-Aware Snapshot Status",
        "## Verification Commands",
        "## Incomplete Items",
    ):
        assert heading in report.markdown

    assert "Completion status: complete" in report.markdown
    assert "- None." in report.markdown
    blank_status_pattern = r"status:$|pytest:$|ruff check \.:$|Commit:$"
    assert not re.search(blank_status_pattern, report.markdown, re.MULTILINE)


def _load_writer() -> object:
    spec = importlib.util.spec_from_file_location("write_readiness_report", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load readiness writer: {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
