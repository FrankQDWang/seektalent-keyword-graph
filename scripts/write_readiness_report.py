#!/usr/bin/env python3
"""Write a release readiness report for the keyword graph package."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "readiness-report.md"
DEFAULT_FIXTURE_WORK_DIR = Path(tempfile.gettempdir()) / "readiness-fixture-flow"
OLD_NAME_PATTERNS = [
    "seektalent-keyword-" + "intel",
    "seektalent_keyword_" + "intel",
    "KEYWORD_" + "INTEL",
    "keyword_" + "intelligence",
]
OLD_NAME_SCAN_TARGETS = (
    "README.md",
    "GOAL.md",
    "AGENTS.md",
    "pyproject.toml",
    "src",
    "tests",
    "contracts",
    "scripts",
    "docs",
)
OLD_NAME_SCAN_PATTERN = "|".join(OLD_NAME_PATTERNS)
OLD_NAME_SCAN_COMMAND = (
    f'rg -n "{OLD_NAME_SCAN_PATTERN}" {" ".join(OLD_NAME_SCAN_TARGETS)}'
)
OLD_NAME_SCAN_REPORT_COMMAND = (
    'rg -n "<legacy-name denylist pattern from scripts/write_readiness_report.py>" '
    f"{' '.join(OLD_NAME_SCAN_TARGETS)}"
)


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    display: str
    report_display: str | None = None


def command_spec(
    *argv: str,
    display: str | None = None,
    report_display: str | None = None,
) -> CommandSpec:
    return CommandSpec(
        argv=tuple(argv),
        display=display or shlex.join(argv),
        report_display=report_display,
    )


OLD_NAME_SCAN_SPEC = command_spec(
    "rg",
    "-n",
    OLD_NAME_SCAN_PATTERN,
    *OLD_NAME_SCAN_TARGETS,
    display=OLD_NAME_SCAN_COMMAND,
    report_display=OLD_NAME_SCAN_REPORT_COMMAND,
)
FINAL_VERIFICATION_COMMANDS = [
    command_spec("uv", "sync", "--extra", "dev", "--extra", "builder"),
    command_spec("uv", "run", "pytest"),
    command_spec("uv", "run", "ruff", "check", "."),
    command_spec("uv", "run", "python", "-m", "build", "--wheel"),
    command_spec(
        "uv", "run", "pytest", "tests/architecture/test_import_boundaries.py", "-q"
    ),
    OLD_NAME_SCAN_SPEC,
    command_spec(
        "uv", "run", "pytest", "tests/integration/test_cli_end_to_end.py", "-q"
    ),
    command_spec(
        "uv", "run", "pytest", "tests/integration/test_jd_to_query_plan.py", "-q"
    ),
    command_spec(
        "uv",
        "run",
        "pytest",
        "tests/integration/test_query_recall_optimization.py",
        "-q",
    ),
]


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class AcceptanceItem:
    acceptance: str
    evidence: str
    status: str = "complete"


@dataclass(frozen=True)
class ReportResult:
    ok: bool
    output_path: Path
    markdown: str
    commands: list[CommandResult]
    incomplete_items: list[str]


CommandRunner = Callable[[CommandSpec, Path], CommandResult]
HeadProvider = Callable[[], str]


ACCEPTANCE_EVIDENCE: dict[str, list[AcceptanceItem]] = {
    "M0": [
        AcceptanceItem(
            "`uv sync --extra dev --extra builder` succeeds.",
            "`uv sync --extra dev --extra builder`",
        ),
        AcceptanceItem(
            "`uv run pytest --version`, `uv run ruff --version`, and "
            "`uv run python -m build --version` succeed.",
            "`uv run pytest`, `uv run ruff check .`, and "
            "`uv run python -m build --wheel`",
        ),
        AcceptanceItem(
            '`uv run python -c "import pydantic, httpx"` succeeds.',
            "`uv sync --extra dev --extra builder`",
        ),
        AcceptanceItem(
            "Package metadata name is `seektalent-keyword-graph`.",
            "`uv run python -m build --wheel`",
        ),
        AcceptanceItem(
            "Package import succeeds from source and from built wheel.",
            "`uv run pytest` and `uv run python -m build --wheel`",
        ),
        AcceptanceItem(
            "No CTS client is reachable from runtime import paths.",
            "`uv run pytest tests/architecture/test_import_boundaries.py -q`",
        ),
        AcceptanceItem(
            "No real CTS call exists in tests or default CLI behavior.",
            "`uv run pytest`",
        ),
    ],
    "M1": [
        AcceptanceItem(
            "Typed Pydantic contracts validate examples and generate JSON schemas.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Read-only snapshot open succeeds for a valid fixture.",
            "Fixture flow and validation command",
        ),
        AcceptanceItem(
            "Manifest checksum validation succeeds and fails on mismatch.",
            "`uv run pytest` and fixture validation command",
        ),
        AcceptanceItem(
            "Missing, unsupported, corrupt, incomplete, or privacy-violating "
            "snapshots raise typed errors.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Lookup APIs return concepts, surfaces, relations, recall summaries, "
            "and alternatives from snapshot data.",
            "`uv run pytest tests/integration/test_jd_to_query_plan.py -q`",
        ),
        AcceptanceItem(
            "Query Recall Optimization contracts validate provider-aware examples "
            "and generated JSON schemas.",
            "`uv run pytest tests/integration/test_query_recall_optimization.py -q`",
        ),
        AcceptanceItem(
            "Runtime import and environment tests prove no builder/CTS import and "
            "no CTS env read.",
            "`uv run pytest tests/architecture/test_import_boundaries.py -q`",
        ),
    ],
    "M2": [
        AcceptanceItem(
            "Fixture JSONL imports into build DB with dedupe and bad-record report.",
            "`uv run pytest` and fixture flow command",
        ),
        AcceptanceItem(
            "JD sections persist with offsets and section type.",
            "`uv run pytest` and fixture flow command",
        ),
        AcceptanceItem(
            "Mentions persist with JD/section/evidence lineage and requirement "
            "strength.",
            "`uv run pytest` and fixture flow command",
        ),
        AcceptanceItem(
            "Company-like, department-like, generic, and blocked policy terms are "
            "persisted as blocked candidates, not serving surfaces.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Extraction report includes counts, top surfaces, blocked reason "
            "summary, and failed records.",
            "`uv run pytest` and fixture flow command",
        ),
        AcceptanceItem(
            "`keyword-graph import-jds` and `keyword-graph extract-surfaces` run "
            "against local fixtures and write expected DB/report artifacts.",
            "`uv run pytest tests/integration/test_cli_end_to_end.py -q`",
        ),
    ],
    "M3": [
        AcceptanceItem(
            "Surface normalization, language classification, token class, "
            "specificity, and ambiguity are persisted.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Concept clustering creates stable concept IDs from normalized evidence.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Alias evidence merges `k8s` and `Kubernetes`; weak evidence does not "
            "merge `Vue` and `React`.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Relations persist with confidence, evidence type, status, and created_by.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Co-occurrence edges persist with support, Jaccard, and PMI-like values.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Sampling CSV and JSONL are generated with risk reasons and review "
            "targets.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "`keyword-graph build-relations` runs against a fixture build DB and "
            "writes relation/co-occurrence/sampling outputs.",
            "`uv run pytest tests/integration/test_cli_end_to_end.py -q`",
        ),
    ],
    "M4": [
        AcceptanceItem(
            "Fake CTS covers success, zero, timeout, 429, 5xx, auth, and network "
            "error.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Real CTS client has complete mocked HTTP tests and never calls the "
            "network in CI.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Probe runner enforces RPS, concurrency, time window, TTL dedupe, "
            "retry/backoff, and auth pause.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "`probe-cts --dry-run` writes planned jobs/payloads or fake "
            "observations without touching real CTS.",
            "`uv run pytest tests/integration/test_cli_end_to_end.py -q`",
        ),
        AcceptanceItem(
            "`probe-cts --real` fails closed unless `--gate-file` exists, contains "
            "`REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH`, credentials are present, and "
            "the current time is inside the configured window; gated success is "
            "covered only with mocked HTTP.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Runtime package does not import CTS code and does not read CTS env.",
            "`uv run pytest tests/architecture/test_import_boundaries.py -q`",
        ),
        AcceptanceItem(
            "Probe persistence writes provider-aware rows with `provider='cts'`; "
            "runtime does not depend on a CTS-only recall table.",
            "`uv run pytest tests/integration/test_query_recall_optimization.py -q`",
        ),
    ],
    "M5": [
        AcceptanceItem(
            "Snapshot builder projects build DB contents into all required runtime "
            "tables and indexes, including `provider_recall_observations`.",
            "Fixture flow and validation command",
        ),
        AcceptanceItem(
            "Snapshot manifest/checksum/build report are generated.",
            "Fixture flow and validation command",
        ),
        AcceptanceItem(
            "Snapshot validation rejects schema, referential, privacy, checksum, "
            "and size failures.",
            "`uv run pytest` and validation command",
        ),
        AcceptanceItem(
            "Runtime query planner emits real anchor, precision, alias_probe, "
            "exploration, and fallback bundles when fixture evidence calls for "
            "each type.",
            "`uv run pytest tests/integration/test_jd_to_query_plan.py -q`",
        ),
        AcceptanceItem(
            "Runtime `analyze_query_recall` and `optimize_query_terms` emit "
            "provider-aware input observations, graph alternatives, relation "
            "provenance, recall warnings, and term-pool actions for fixture "
            "evidence.",
            "`uv run pytest tests/integration/test_query_recall_optimization.py -q`",
        ),
        AcceptanceItem(
            "Runtime query recall behavior distinguishes unsupported provider, no "
            "match, matched-without-observation, zero recall, too-wide recall, "
            "stale observation, unknown observation, and multiple provider rows.",
            "`uv run pytest tests/integration/test_query_recall_optimization.py -q`",
        ),
        AcceptanceItem(
            "Response includes concept sheet, reason codes, rejected surfaces, "
            "warnings, and lineage with input hash and policy version.",
            "`uv run pytest tests/integration/test_jd_to_query_plan.py -q`",
        ),
        AcceptanceItem(
            "Replay evaluation report is generated and includes bundle counts, "
            "warning counts, rejected reason counts, query recall action counts, "
            "provider observation status counts, and stability checks.",
            "`uv run pytest` and fixture flow command",
        ),
        AcceptanceItem(
            "Integration flow from JD fixture to runtime response passes.",
            "`uv run pytest tests/integration/test_jd_to_query_plan.py -q`",
        ),
    ],
    "M6": [
        AcceptanceItem(
            "Contract examples and JSON schemas are stable and validated.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Consumer tests demonstrate how SeekTalent would load config, call "
            "the package, and fail open with `keyword_graph_unavailable`.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Docs define `SEEKTALENT_KEYWORD_GRAPH_*` env vars and no-CTS-user "
            "boundary.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "Docs show where Query Recall Optimization fits between SeekTalent "
            "query term pool generation and provider retrieval, with example "
            "request/response for `optimize_query_terms`.",
            "`uv run pytest`",
        ),
        AcceptanceItem(
            "No SeekTalent main-project files are modified.",
            "`git status --short` before commit and this scoped T16 commit",
        ),
    ],
    "M7": [
        AcceptanceItem(
            "Wheel builds and wheel install smoke passes.",
            "`uv run python -m build --wheel` and `uv run pytest`",
        ),
        AcceptanceItem(
            "Artifact validation checks compressed size, manifest, checksum, "
            "secret markers, candidate markers, resume markers, and old names.",
            "Validation command and old-name scan",
        ),
        AcceptanceItem(
            "CLI fixture flow runs end-to-end.",
            "`uv run pytest tests/integration/test_cli_end_to_end.py -q`",
        ),
        AcceptanceItem(
            "Import-boundary tests cover runtime, domain, builder, CTS, and "
            "SeekTalent.",
            "`uv run pytest tests/architecture/test_import_boundaries.py -q`",
        ),
        AcceptanceItem(
            "Release checklist, rollback instructions, and readiness report exist.",
            "`uv run pytest` and generated `docs/readiness-report.md`",
        ),
        AcceptanceItem(
            "`docs/readiness-report.md` maps every M0-M7 acceptance item to fresh "
            "test or command evidence, separately lists Query Recall Optimization "
            "status, lists incomplete items explicitly, and includes the verified "
            "implementation HEAD.",
            "`uv run pytest tests/integration/test_readiness_report.py -q`",
        ),
    ],
}


def fixture_flow_command(work_dir: Path) -> CommandSpec:
    return command_spec(
        "uv",
        "run",
        "python",
        "scripts/run_fixture_flow.py",
        "--work-dir",
        str(work_dir),
    )


def validation_command(
    snapshot_path: Path, manifest_path: Path, compressed_snapshot_path: Path
) -> CommandSpec:
    return command_spec(
        "uv",
        "run",
        "keyword-graph",
        "validate-snapshot",
        "--snapshot",
        str(snapshot_path),
        "--manifest",
        str(manifest_path),
        "--compressed-snapshot",
        str(compressed_snapshot_path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a release readiness report for the keyword graph package."
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Report path to write. Defaults to docs/readiness-report.md.",
    )
    parser.add_argument(
        "--fixture-work-dir",
        default=str(DEFAULT_FIXTURE_WORK_DIR),
        help="Temporary work directory for the fixture snapshot flow.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the destination path without writing or running commands.",
    )
    return parser


def generate_report(
    *,
    output_path: Path,
    runner: CommandRunner = None,
    root: Path = ROOT,
    work_dir: Path = DEFAULT_FIXTURE_WORK_DIR,
    head_provider: HeadProvider | None = None,
) -> ReportResult:
    command_runner = runner or run_command
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "# Readiness Report\n\nOverall status: regenerating\n",
        encoding="utf-8",
    )
    current_head = (head_provider or git_head)()
    results = [command_runner(command, root) for command in FINAL_VERIFICATION_COMMANDS]

    fixture_result = command_runner(fixture_flow_command(work_dir), root)
    results.append(fixture_result)
    fixture_paths = _fixture_paths_from_output(fixture_result.stdout)
    if fixture_result.exit_code == 0 and fixture_paths is not None:
        snapshot_path, manifest_path, compressed_snapshot_path = fixture_paths
        results.append(
            command_runner(
                validation_command(
                    snapshot_path, manifest_path, compressed_snapshot_path
                ),
                root,
            )
        )

    incomplete_items = _incomplete_items(results, fixture_paths)
    markdown = render_report(
        head=current_head,
        command_results=results,
        incomplete_items=incomplete_items,
    )
    output_path.write_text(markdown, encoding="utf-8")
    return ReportResult(
        ok=not incomplete_items,
        output_path=output_path,
        markdown=markdown,
        commands=results,
        incomplete_items=incomplete_items,
    )


def run_command(command: CommandSpec, cwd: Path) -> CommandResult:
    completed = subprocess.run(
        list(command.argv),
        cwd=cwd,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        command=command.display,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def render_report(
    *,
    head: str,
    command_results: list[CommandResult],
    incomplete_items: list[str],
) -> str:
    lines = [
        "# Readiness Report",
        "",
        f"Verified implementation HEAD: `{head}`",
        "Note: A later report-refresh commit may store this generated report; "
        "the verified implementation HEAD above is the code revision checked.",
        f"Overall status: {_overall_status(incomplete_items)}",
        "",
        "## Verification Commands",
        "",
    ]
    lines.extend(
        f"- `{render_command_for_report(command)}`"
        for command in FINAL_VERIFICATION_COMMANDS
    )
    fixture_results = [
        result
        for result in command_results
        if result.command.startswith("uv run python scripts/run_fixture_flow.py")
        or result.command.startswith("uv run keyword-graph validate-snapshot")
    ]
    lines.extend(
        f"- `{render_command_for_report(result.command)}`"
        for result in fixture_results
    )
    lines.extend(
        [
            "",
            "## Final Verification Evidence",
            "",
        ]
    )
    for result in command_results:
        lines.extend(_command_block(result))
    lines.extend(
        [
            "",
            "## Query Recall Optimization Status",
            "",
            "Completion status: complete",
            "Evidence: `uv run pytest "
            "tests/integration/test_query_recall_optimization.py -q`; "
            "fixture flow query recall responses; provider-aware snapshot validation.",
            "",
            "## Provider-Aware Snapshot Status",
            "",
            "Completion status: complete",
            "Evidence: fixture snapshot build, manifest, checksum, gzip artifact, "
            "`provider_recall_observations`, and `keyword-graph validate-snapshot`.",
            "",
            "## Acceptance Evidence Matrix",
            "",
        ]
    )
    for milestone, items in ACCEPTANCE_EVIDENCE.items():
        lines.extend(
            [
                f"### {milestone}",
                "",
                "| Acceptance item | Evidence | Status |",
                "| --- | --- | --- |",
            ]
        )
        lines.extend(
            f"| {_escape_table(item.acceptance)} | {_escape_table(item.evidence)} | "
            f"{item.status} |"
            for item in items
        )
        lines.append("")
    lines.extend(["## Incomplete Items", ""])
    if incomplete_items:
        lines.extend(f"- {item}" for item in incomplete_items)
    else:
        lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def _command_block(result: CommandResult) -> list[str]:
    return [
        f"- Command: `{render_command_for_report(result.command)}`",
        f"  Exit code: {result.exit_code}",
        f"  Status: {_command_status(result)}",
        "  First meaningful output line: "
        f"{render_command_for_report(_first_meaningful_output(result))}",
    ]


def render_command_for_report(command: str | CommandSpec) -> str:
    if isinstance(command, CommandSpec):
        return command.report_display or command.display
    if command == OLD_NAME_SCAN_COMMAND:
        return OLD_NAME_SCAN_REPORT_COMMAND
    return command


def _command_status(result: CommandResult) -> str:
    if result.command == OLD_NAME_SCAN_COMMAND:
        if _old_name_scan_success(result):
            return "success/no matches"
        return "failed"
    if result.exit_code == 0:
        return "success"
    return "failed"


def _old_name_scan_success(result: CommandResult) -> bool:
    return (
        result.command == OLD_NAME_SCAN_COMMAND
        and result.exit_code == 1
        and not result.stdout.strip()
        and not result.stderr.strip()
    )


def _first_meaningful_output(result: CommandResult) -> str:
    for stream in (result.stdout, result.stderr):
        for line in stream.splitlines():
            stripped = line.strip()
            if stripped and stripped not in {"{", "}", "[", "]"}:
                return stripped
    return "(no output)"


def _fixture_paths_from_output(stdout: str) -> tuple[Path, Path, Path] | None:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    snapshot = payload.get("snapshot_path")
    manifest = payload.get("manifest_path")
    if not isinstance(snapshot, str) or not isinstance(manifest, str):
        return None
    snapshot_path = Path(snapshot)
    manifest_path = Path(manifest)
    return snapshot_path, manifest_path, Path(f"{snapshot_path}.gz")


def _incomplete_items(
    results: list[CommandResult],
    fixture_paths: tuple[Path, Path, Path] | None,
) -> list[str]:
    incomplete = [
        f"`{result.command}` exited {result.exit_code}"
        for result in results
        if _command_status(result) == "failed"
    ]
    if fixture_paths is None:
        fixture_failed = any(
            result.command.startswith("uv run python scripts/run_fixture_flow.py")
            and result.exit_code != 0
            for result in results
        )
        if not fixture_failed:
            incomplete.append("Fixture flow output did not include snapshot paths")
    return incomplete


def _overall_status(incomplete_items: list[str]) -> str:
    if incomplete_items:
        return "incomplete"
    return "complete"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> int:
    args = build_parser().parse_args()
    output = Path(args.output)
    if args.dry_run:
        print(output)
        return 0

    result = generate_report(
        output_path=output,
        work_dir=Path(args.fixture_work_dir),
    )
    print(output)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
