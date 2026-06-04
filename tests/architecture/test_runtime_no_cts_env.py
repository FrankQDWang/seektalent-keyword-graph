from __future__ import annotations

import ast
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph"
RUNTIME_ROOTS = (
    SRC_ROOT / "runtime",
    SRC_ROOT / "engine.py",
    SRC_ROOT / "__init__.py",
)
BLOCKED_NETWORK_IMPORT_PREFIXES = (
    "httpx",
    "requests",
    "socket",
    "urllib.request",
    "http.client",
)
BLOCKED_FROM_IMPORT_MEMBERS = {
    "http": {"client"},
    "urllib": {"request"},
}
BLOCKED_NETWORK_CALL_PREFIXES = BLOCKED_NETWORK_IMPORT_PREFIXES


def runtime_module_paths() -> list[Path]:
    paths: list[Path] = []
    for root in RUNTIME_ROOTS:
        if root.is_dir():
            paths.extend(root.rglob("*.py"))
        else:
            paths.append(root)
    return sorted(paths)


def find_runtime_network_offenders(
    paths: Iterable[Path], project_root: Path = PROJECT_ROOT
) -> list[str]:
    offenders: list[str] = []

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_blocked_network_import(alias.name):
                        offenders.append(
                            f"{path.relative_to(project_root)} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                offenders.extend(
                    f"{path.relative_to(project_root)} imports {blocked_name}"
                    for blocked_name in _blocked_from_import_names(node)
                )
            elif isinstance(node, ast.Call):
                call_name = _dotted_name(node.func)
                if call_name is not None and _is_blocked_network_call(call_name):
                    offenders.append(
                        f"{path.relative_to(project_root)} calls {call_name}"
                    )

    return offenders


def _is_blocked_network_import(name: str) -> bool:
    return name == "urllib" or any(
        name == prefix or name.startswith(f"{prefix}.")
        for prefix in BLOCKED_NETWORK_IMPORT_PREFIXES
    )


def _blocked_from_import_names(node: ast.ImportFrom) -> list[str]:
    module = node.module or ""
    if any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in BLOCKED_NETWORK_IMPORT_PREFIXES
    ):
        return [module]

    blocked_names: list[str] = []
    blocked_members = BLOCKED_FROM_IMPORT_MEMBERS.get(module, set())
    for alias in node.names:
        full_name = f"{module}.{alias.name}" if module else alias.name
        if alias.name in blocked_members or _is_blocked_network_import(full_name):
            blocked_names.append(full_name)
    return blocked_names


def _is_blocked_network_call(name: str) -> bool:
    return any(
        name == prefix or name.startswith(f"{prefix}.")
        for prefix in BLOCKED_NETWORK_CALL_PREFIXES
    )


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


def test_runtime_modules_do_not_import_live_provider_or_network_clients() -> None:
    offenders = find_runtime_network_offenders(runtime_module_paths())

    assert offenders == []


def test_runtime_network_scanner_rejects_import_variants(tmp_path: Path) -> None:
    snippets = {
        "requests_submodule.py": "import requests.sessions\n",
        "urllib_package.py": "import urllib\n",
        "urllib_request_from_package.py": "from urllib import request\n",
        "http_client.py": "import http.client\n",
        "http_client_from_package.py": "from http import client\n",
        "socket_submodule.py": "import socket.socket\n",
    }
    paths = []
    for filename, source in snippets.items():
        path = tmp_path / filename
        path.write_text(source, encoding="utf-8")
        paths.append(path)

    offenders = find_runtime_network_offenders(paths, tmp_path)

    assert offenders == [
        "requests_submodule.py imports requests.sessions",
        "urllib_package.py imports urllib",
        "urllib_request_from_package.py imports urllib.request",
        "http_client.py imports http.client",
        "http_client_from_package.py imports http.client",
        "socket_submodule.py imports socket.socket",
    ]


def test_runtime_network_scanner_rejects_obvious_network_call_sites(
    tmp_path: Path,
) -> None:
    path = tmp_path / "network_calls.py"
    path.write_text(
        dedent(
            """
            def calls_network_clients():
                requests.get("https://example.invalid")
                httpx.Client()
                urllib.request.urlopen("https://example.invalid")
                socket.create_connection(("example.invalid", 443))
                http.client.HTTPConnection("example.invalid")
            """
        ),
        encoding="utf-8",
    )

    offenders = find_runtime_network_offenders([path], tmp_path)

    assert offenders == [
        "network_calls.py calls requests.get",
        "network_calls.py calls httpx.Client",
        "network_calls.py calls urllib.request.urlopen",
        "network_calls.py calls socket.create_connection",
        "network_calls.py calls http.client.HTTPConnection",
    ]


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
