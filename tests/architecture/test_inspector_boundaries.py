from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INSPECTOR_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph" / "inspector"


def test_inspector_import_paths_do_not_reach_builder_cts_or_seektalent() -> None:
    blocked_internal_prefixes = (
        "seektalent_keyword_graph.builder",
        "seektalent_keyword_graph.cts",
    )
    blocked_external_roots = {"seektalent", "SeekTalent"}
    offenders: list[str] = []
    for path in sorted(INSPECTOR_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(
                        blocked_internal_prefixes
                    ) or alias.name.split(".", maxsplit=1)[0] in blocked_external_roots:
                        offenders.append(
                            f"{path.relative_to(PROJECT_ROOT)} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(
                    blocked_internal_prefixes
                ) or module.split(".", maxsplit=1)[0] in blocked_external_roots:
                    offenders.append(
                        f"{path.relative_to(PROJECT_ROOT)} imports {module}"
                    )

    assert offenders == []


def test_inspector_source_does_not_reference_cts_environment() -> None:
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} mentions KEYWORD_GRAPH_CTS_"
        for path in sorted(INSPECTOR_ROOT.rglob("*.py"))
        if "KEYWORD_GRAPH_CTS_" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_inspector_query_handling_does_not_import_builder_cts_or_open_network() -> None:
    env = os.environ.copy()
    env["KEYWORD_GRAPH_CTS_TENANT_SECRET"] = "must-not-be-read"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _INSPECTOR_BOUNDARY_SCRIPT,
        ],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert completed.stdout.strip() == "React.js"


_INSPECTOR_BOUNDARY_SCRIPT = r"""
import os
import socket
import sys

os.environ["KEYWORD_GRAPH_CTS_API_KEY"] = "must-not-be-read"
original_getenv = os.getenv


def guarded_getenv(key, default=None):
    if key.startswith("KEYWORD_GRAPH_CTS_"):
        raise AssertionError(f"inspector read forbidden CTS env var {key}")
    return original_getenv(key, default)


OriginalSocket = socket.socket


class GuardedSocket(OriginalSocket):
    def __new__(cls, *args, **kwargs):
        raise AssertionError("inspector query handling attempted network I/O")


def forbidden_modules():
    return {
        name
        for name in sys.modules
        if name == "seektalent"
        or name.startswith(
            (
                "seektalent_keyword_graph.builder",
                "seektalent_keyword_graph.cts",
            )
        )
    }


os.getenv = guarded_getenv
before = forbidden_modules()

from seektalent_keyword_graph.inspector.server import (
    InspectorApp,
    InspectorServerConfig,
    query_recall_payload,
)

if forbidden_modules() != before:
    raise AssertionError("inspector import loaded builder, CTS, or SeekTalent modules")

socket.socket = GuardedSocket
app = InspectorApp.open(InspectorServerConfig(port=0))
try:
    payload = query_recall_payload(
        app,
        {"provider": "cts", "query_text": "React", "query_mode": "keyword"},
    )
finally:
    app.close()

if forbidden_modules() != before:
    raise AssertionError("inspector query loaded builder, CTS, or SeekTalent modules")

print(payload["response"]["recommendations"][0]["recommended_query_text"])
"""
