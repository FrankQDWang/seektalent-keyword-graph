from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from seektalent_keyword_graph.inspector.server import (
    InspectorServerConfig,
    InspectorStartupError,
    create_server,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def fixture_flow_result(tmp_path_factory: pytest.TempPathFactory) -> Any:
    loader_path = ROOT / "tests" / "integration" / "_fixture_flow_loader.py"
    spec = importlib.util.spec_from_file_location("inspector_api_fixture", loader_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_run_fixture_flow()(tmp_path_factory.mktemp("inspector-api"))


@contextmanager
def running_server(config: InspectorServerConfig) -> Iterator[str]:
    server = create_server(config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def post_json(url: str, payload: dict[str, object] | str) -> tuple[int, dict[str, Any]]:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    request = urllib.request.Request(
        url,
        data=data.encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def raw_post(
    host: str,
    port: int,
    *,
    content_length: str,
    body: bytes,
) -> tuple[int, dict[str, Any]]:
    request = (
        b"POST /api/query-recall HTTP/1.1\r\n"
        + f"Host: {host}:{port}\r\n".encode("ascii")
        + b"Content-Type: application/json\r\n"
        + f"Content-Length: {content_length}\r\n".encode("ascii")
        + b"Connection: close\r\n"
        + b"\r\n"
        + body
    )
    with socket.create_connection((host, port), timeout=5) as client:
        client.settimeout(5)
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        response = b""
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            response += chunk

    header, raw_body = response.split(b"\r\n\r\n", maxsplit=1)
    status_line = header.splitlines()[0].decode("ascii")
    status = int(status_line.split()[1])
    return status, json.loads(raw_body.decode("utf-8"))


@pytest.fixture(scope="module")
def inspector_base_url(fixture_flow_result: Any) -> Iterator[str]:
    config = InspectorServerConfig(
        port=0,
        snapshot_path=fixture_flow_result.snapshot_path,
        manifest_path=fixture_flow_result.manifest_path,
    )
    with running_server(config) as base_url:
        yield base_url


def test_query_recall_react_returns_input_observation_alias_and_recommendation(
    inspector_base_url: str,
) -> None:
    status, payload = post_json(
        f"{inspector_base_url}/api/query-recall",
        {
            "provider": "cts",
            "query_text": "React",
            "query_mode": "keyword",
            "max_alternatives": 10,
        },
    )

    assert status == 200
    response = payload["response"]
    observation = response["input_observations"][0]
    assert observation["query_text"] == "React"
    assert observation["provider"] == "cts"
    assert observation["query_mode"] == "keyword"
    assert observation["total"] == 0
    assert observation["status"] == "ok"
    assert observation["recall_bucket"] == "zero"
    assert observation["observed_at"] == "2026-06-01T00:00:00Z"
    assert observation["observation_id"] == "obs:cts:surface:react"
    assert observation["evidence_ref"] == "eval:cts:surface:react"

    react_js = next(
        alternative
        for alternative in response["alternatives"]
        if alternative["query_text"] == "React.js"
    )
    assert react_js["relation_type"] == "alias"
    assert react_js["confidence"] == 0.95
    assert react_js["source_concept_id"] == "concept:react"
    assert react_js["source_surface_id"] == "surface:react"
    assert react_js["target_surface_id"] == "surface:react.js"
    assert react_js["observation"]["recall_bucket"] == "healthy"
    assert react_js["observation"]["total"] == 42
    assert response["recommendations"][0]["action"] == "add_alias_probe"
    assert response["recommendations"][0]["recommended_query_text"] == "React.js"


def test_query_recall_kubernetes_returns_precision_companion(
    inspector_base_url: str,
) -> None:
    status, payload = post_json(
        f"{inspector_base_url}/api/query-recall",
        {
            "provider": "cts",
            "query_text": "Kubernetes",
            "query_mode": "keyword",
            "max_alternatives": 10,
        },
    )

    assert status == 200
    response = payload["response"]
    assert response["input_observations"][0]["recall_bucket"] == "too_wide"
    assert response["input_observations"][0]["total"] == 1500
    assert response["recommendations"][0]["action"] == "add_precision_companion"
    assert response["recommendations"][0]["recommended_query_text"] == "Docker"
    docker = next(
        alternative
        for alternative in response["alternatives"]
        if alternative["query_text"] == "Docker"
    )
    assert docker["relation_type"] == "cooccurrence"
    assert docker["observation"]["recall_bucket"] == "healthy"


def test_query_recall_kafka_and_llmops_cover_stale_and_unknown(
    inspector_base_url: str,
) -> None:
    kafka_status, kafka_payload = post_json(
        f"{inspector_base_url}/api/query-recall",
        {"provider": "cts", "query_text": "Kafka", "query_mode": "keyword"},
    )
    llmops_status, llmops_payload = post_json(
        f"{inspector_base_url}/api/query-recall",
        {"provider": "cts", "query_text": "LLMOps", "query_mode": "keyword"},
    )

    assert kafka_status == 200
    kafka = kafka_payload["response"]
    assert kafka["input_observations"][0]["recall_bucket"] == "stale"
    assert kafka["recommendations"][0]["action"] == "replace"
    assert kafka["recommendations"][0]["recommended_query_text"] == "Apache Kafka"

    assert llmops_status == 200
    llmops = llmops_payload["response"]
    assert llmops["input_observations"][0]["status"] == "unknown"
    assert llmops["input_observations"][0]["recall_bucket"] == "unknown"
    assert llmops["recommendations"][0]["action"] == "score_only"


@pytest.mark.parametrize(
    ("payload", "expected_status", "expected_code"),
    [
        ({"provider": "lagou", "query_text": "React"}, 400, "unsupported_provider"),
        ({"provider": "cts", "query_text": "GhostLang"}, 404, "no_match"),
        (
            {
                "provider": "cts",
                "query_text": "Vector Search",
                "query_mode": "phrase",
            },
            409,
            "matched_without_observation",
        ),
        ({"provider": "cts", "query_text": ""}, 400, "invalid_request"),
    ],
)
def test_query_recall_errors_use_stable_shape(
    inspector_base_url: str,
    payload: dict[str, object],
    expected_status: int,
    expected_code: str,
) -> None:
    status, body = post_json(f"{inspector_base_url}/api/query-recall", payload)

    assert status == expected_status
    assert set(body) == {"error"}
    assert body["error"]["code"] == expected_code
    assert body["error"]["message"]
    assert isinstance(body["error"]["details"], dict)
    if expected_code in {"no_match", "matched_without_observation"}:
        response = body["error"]["details"]["response"]
        assert response["recommendations"]
        assert response["warnings"]


def test_invalid_json_request_uses_invalid_request_error(
    inspector_base_url: str,
) -> None:
    status, body = post_json(f"{inspector_base_url}/api/query-recall", "{bad json")

    assert status == 400
    assert body == {
        "error": {
            "code": "invalid_request",
            "message": "Request body must be valid JSON.",
            "details": {},
        }
    }


@pytest.mark.parametrize(
    ("content_length", "body"),
    [
        (
            "-1",
            b'{"provider":"cts","query_text":"'
            + (b"GhostLang" * 9000)
            + b'"}',
        ),
        ("65537", b"{}"),
        ("not-an-int", b"{}"),
    ],
    ids=("negative", "oversized", "malformed"),
)
def test_invalid_content_length_uses_invalid_request_error(
    fixture_flow_result: Any,
    content_length: str,
    body: bytes,
) -> None:
    config = InspectorServerConfig(
        port=0,
        snapshot_path=fixture_flow_result.snapshot_path,
        manifest_path=fixture_flow_result.manifest_path,
    )
    with running_server(config) as base_url:
        parsed = urllib.parse.urlparse(base_url)
        assert parsed.hostname is not None
        assert parsed.port is not None
        status, payload = raw_post(
            parsed.hostname,
            parsed.port,
            content_length=content_length,
            body=body,
        )

    assert status == 400
    assert payload["error"]["code"] == "invalid_request"
    assert payload["error"]["message"] == (
        "content-length must be between 1 and 65536 bytes"
    )


def test_invalid_snapshot_startup_uses_invalid_snapshot_code(tmp_path: Path) -> None:
    invalid_snapshot = tmp_path / "keyword-graph.sqlite3"
    invalid_snapshot.write_text("not sqlite", encoding="utf-8")

    with pytest.raises(InspectorStartupError) as exc_info:
        create_server(
            InspectorServerConfig(port=0, snapshot_path=invalid_snapshot)
        )

    assert exc_info.value.code == "invalid_snapshot"
    assert "invalid SQLite snapshot" in str(exc_info.value)
    assert exc_info.value.details == {"snapshot_path": str(invalid_snapshot)}
