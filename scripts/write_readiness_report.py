#!/usr/bin/env python3
"""Write a release readiness report for the keyword graph package."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "readiness-report.md"


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
        "--dry-run",
        action="store_true",
        help="Print the destination path without writing the report.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = Path(args.output)
    if args.dry_run:
        print(output)
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "# Readiness Report\n\n"
        "status: pending\n\n"
        "This scaffold is expanded by the T16 final verification slice.\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
