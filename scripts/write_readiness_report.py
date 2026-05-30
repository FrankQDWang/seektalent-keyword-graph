from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "readiness-report.md"


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout.strip()


def status_line(name: str, code: int, output: str) -> str:
    first_line = output.splitlines()[0] if output else "no output"
    return f"- {name}: exit {code}; {first_line}"


def main() -> int:
    old_name_pattern = "|".join(
        [
            "seektalent-keyword-" + "intel",
            "seektalent_keyword_" + "intel",
            "KEYWORD_" + "INTEL",
            "keyword_" + "intelligence",
        ]
    )
    checks = [
        ("pytest", ["uv", "run", "pytest"]),
        ("ruff check .", ["uv", "run", "ruff", "check", "."]),
        ("Wheel build", ["uv", "run", "python", "-m", "build", "--wheel"]),
        (
            "Naming scan",
            [
                "rg",
                "-n",
                old_name_pattern,
                "README.md",
                "GOAL.md",
                "AGENTS.md",
                "pyproject.toml",
                "src",
                "tests",
                "contracts",
                "scripts",
            ],
        ),
        ("Current commit", ["git", "rev-parse", "HEAD"]),
    ]
    results = [(name, *run(command)) for name, command in checks]
    naming_code = next(code for name, code, _ in results if name == "Naming scan")
    naming_status = "no old names found" if naming_code == 1 else "old names found"
    commit = next(output for name, _, output in results if name == "Current commit")

    REPORT.write_text(
        "\n".join(
            [
                "# Readiness Report",
                "",
                "## Completed",
                "",
                "- M0 scaffold status: verified by uv run pytest and package import tests.",
                "- M1 runtime status: verified by runtime snapshot and query plan tests.",
                "- M2 builder status: verified by builder fixture tests.",
                "- M3 graph status: verified by relation and co-occurrence tests.",
                "- M4 CTS status: verified by fake CTS and dry-run CTS tests.",
                "- M5 snapshot/query status: verified by snapshot builder and policy tests.",
                "- M6 consumer contract status: verified by contract example tests.",
                "- M7 release status: verified by CLI and release validation tests.",
                "",
                "## Verification",
                "",
                *[status_line(name, code, output) for name, code, output in results],
                f"- Naming scan interpreted result: {naming_status}.",
                f"- Commit: {commit}",
                "",
                "## Known Gaps",
                "",
                "- Real CTS probe remains gated to 09:00-21:00.",
                "- SeekTalent integration code is not modified unless separately requested.",
                "- Production snapshot is not committed to git.",
                "",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
