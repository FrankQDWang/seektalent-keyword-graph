from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph"


def production_python_files() -> list[Path]:
    assert SRC_ROOT.is_dir(), f"production source package is missing: {SRC_ROOT}"

    files = sorted(SRC_ROOT.rglob("*.py"))
    assert files, f"no production Python files found under {SRC_ROOT}"
    return files


def test_production_code_has_no_placeholder_bodies() -> None:
    offenders: list[str] = []

    for path in production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                location = f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                offenders.append(f"{location} uses pass")
            if (
                isinstance(node, ast.Raise)
                and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "NotImplementedError"
            ):
                location = f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}"
                offenders.append(f"{location} raises NotImplementedError")

    assert offenders == []


def test_production_code_has_no_textual_shortcut_markers() -> None:
    blocked_markers = ("TODO", "FIXME", "XXX", "NotImplementedError")
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} contains {marker}"
        for path in production_python_files()
        for marker in blocked_markers
        if marker in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
