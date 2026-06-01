from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph"
RUNTIME_ROOTS = (
    SRC_ROOT / "runtime",
    SRC_ROOT / "engine.py",
    SRC_ROOT / "__init__.py",
)


def runtime_module_paths() -> list[Path]:
    paths: list[Path] = []
    for root in RUNTIME_ROOTS:
        if root.is_dir():
            paths.extend(root.rglob("*.py"))
        else:
            paths.append(root)
    return sorted(paths)


def test_runtime_modules_do_not_import_live_provider_or_network_clients() -> None:
    blocked_exact = {"httpx", "requests", "socket", "urllib.request"}
    offenders: list[str] = []

    for path in runtime_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in blocked_exact:
                        offenders.append(
                            f"{path.relative_to(PROJECT_ROOT)} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module in blocked_exact:
                offenders.append(
                    f"{path.relative_to(PROJECT_ROOT)} imports {node.module}"
                )

    assert offenders == []


def test_runtime_modules_do_not_reference_builder_or_cts_modules() -> None:
    blocked = (
        "seektalent_keyword_graph.builder",
        "seektalent_keyword_graph.cts",
    )
    offenders: list[str] = []

    for path in runtime_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(blocked)
            ):
                offenders.append(
                    f"{path.relative_to(PROJECT_ROOT)} references {node.value}"
                )

    assert offenders == []


def test_package_import_does_not_read_cts_environment() -> None:
    env = os.environ.copy()
    env["KEYWORD_GRAPH_CTS_TENANT_SECRET"] = "must-not-be-read"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            r"""
import os

original_getenv = os.getenv

def guarded_getenv(key, default=None):
    if key.startswith("KEYWORD_GRAPH_CTS_"):
        raise AssertionError(f"read forbidden CTS env var {key}")
    return original_getenv(key, default)

os.getenv = guarded_getenv
import seektalent_keyword_graph
print(seektalent_keyword_graph.__version__)
""",
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert completed.stdout.strip()
