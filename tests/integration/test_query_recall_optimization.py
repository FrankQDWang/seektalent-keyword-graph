from __future__ import annotations

import os
import socket
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

from seektalent_keyword_graph.contracts import QueryRecallRequest
from seektalent_keyword_graph.engine import KeywordGraph


def test_keyword_graph_query_recall_optimization_is_local_only(
    tmp_path: Path, monkeypatch
) -> None:
    runtime_fixtures = _load_runtime_fixtures()

    snapshot_store = runtime_fixtures.open_test_snapshot(tmp_path)
    snapshot_path = snapshot_store.path
    snapshot_store.close()

    monkeypatch.setenv("KEYWORD_GRAPH_CTS_TENANT_SECRET", "do-not-read")
    original_getenv = os.getenv

    def guarded_getenv(key: str, default: str | None = None) -> str | None:
        if key.startswith("KEYWORD_GRAPH_CTS_"):
            raise AssertionError(f"runtime read forbidden CTS env var {key}")
        return original_getenv(key, default)

    def guarded_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("runtime query recall attempted network I/O")

    monkeypatch.setattr(os, "getenv", guarded_getenv)
    monkeypatch.setattr(socket, "socket", guarded_socket)
    forbidden_modules_before = _forbidden_runtime_modules()

    graph = KeywordGraph.open(snapshot_path)
    try:
        response = graph.optimize_query_terms(
            QueryRecallRequest(
                request_id="req-integration-qro",
                provider="cts",
                query_terms=[
                    {"text": "React"},
                    {"text": "Kubernetes"},
                    {"text": "Kafka"},
                    {"text": "LLMOps", "strength": "preferred"},
                    {"text": "GraphQL", "strength": "preferred"},
                ],
                max_alternatives=10,
            )
        )
    finally:
        graph.close()

    assert [
        (term.source_query_text, term.query_text, term.action)
        for term in response.optimized_terms
    ] == [
        ("React", "React.js", "replace"),
        ("Kubernetes", "Docker", "add_precision_companion"),
        ("Kafka", "Apache Kafka", "replace"),
        ("LLMOps", "LLMOps", "score_only"),
        ("GraphQL", "GraphQL", "fallback"),
    ]
    assert [warning.code for warning in response.warnings] == [
        "no_match",
        "zero_recall",
        "too_wide_recall",
        "stale_observation",
        "unknown_observation",
        "fallback",
    ]
    assert _forbidden_runtime_modules() == forbidden_modules_before


def _load_runtime_fixtures() -> ModuleType:
    fixture_path = Path(__file__).parents[1] / "runtime" / "conftest.py"
    spec = spec_from_file_location("runtime_query_recall_fixtures", fixture_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _forbidden_runtime_modules() -> set[str]:
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
