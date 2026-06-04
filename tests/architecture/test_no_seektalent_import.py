from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph"


def test_package_modules_do_not_import_seektalent_main_project() -> None:
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_seektalent_module(alias.name):
                        offenders.append(
                            f"{path.relative_to(PROJECT_ROOT)} imports {alias.name}"
                        )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
                and _is_seektalent_module(node.module)
            ):
                offenders.append(
                    f"{path.relative_to(PROJECT_ROOT)} imports {node.module}"
                )

    assert offenders == []


def _is_seektalent_module(module: str) -> bool:
    return module in {"SeekTalent", "seektalent"} or module.startswith(
        ("SeekTalent.", "seektalent.")
    )
