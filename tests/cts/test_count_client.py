from __future__ import annotations

import json
import socket

import httpx
import pytest

from seektalent_keyword_graph.cts.config import CtsClientConfig
from seektalent_keyword_graph.cts.count_client import CtsCountClient


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("tests must not open real network sockets")

    monkeypatch.setattr(socket, "socket", fail_socket)


def config() -> CtsClientConfig:
    return CtsClientConfig(
        base_url="https://cts.invalid",
        tenant_key="tenant-key",
        tenant_secret="super-secret",
        timeout_seconds=1.5,
        api_version="v1",
        trace_id="trace-123",
    )


def test_real_client_payload_uses_count_only_pagination() -> None:
    seen_payloads: list[dict[str, object]] = []
    seen_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        seen_headers.append(request.headers)
        return httpx.Response(
            200, json={"data": {"total": 12, "items": [{"id": "c1"}]}}
        )

    client = CtsCountClient(config(), transport=httpx.MockTransport(handler))

    result = client.count("python")

    assert result.total == 12
    assert result.status == "ok"
    assert seen_payloads == [
        {"query": "python", "queryMode": "keyword", "page": 1, "pageSize": 1}
    ]
    assert seen_headers[0]["x-trace-id"] == "trace-123"


def test_response_parser_reads_only_data_total_and_ignores_candidate_items() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "total": 7,
                    "items": [{"id": "candidate", "name": "must not leak"}],
                }
            },
        )

    client = CtsCountClient(config(), transport=httpx.MockTransport(handler))

    result = client.count("python")

    assert result.total == 7
    assert result.status == "ok"
    assert not hasattr(result, "items")
    assert not hasattr(result, "candidates")


@pytest.mark.parametrize(
    ("response", "expected_status", "expected_error", "retryable"),
    [
        (
            httpx.Response(400, json={"error": "bad query"}),
            "invalid_query",
            "invalid_query",
            False,
        ),
        (
            httpx.Response(401, json={"error": "auth"}),
            "auth_error",
            "auth_error",
            False,
        ),
        (
            httpx.Response(403, json={"error": "auth"}),
            "auth_error",
            "auth_error",
            False,
        ),
        (httpx.Response(429, json={"error": "rate"}), "rate_limited", "http_429", True),
        (httpx.Response(503, json={"error": "down"}), "server_error", "http_5xx", True),
    ],
)
def test_real_client_classifies_http_statuses(
    response: httpx.Response,
    expected_status: str,
    expected_error: str,
    retryable: bool,
) -> None:
    client = CtsCountClient(
        config(), transport=httpx.MockTransport(lambda _request: response)
    )

    result = client.count("python")

    assert result.status == expected_status
    assert result.error_code == expected_error
    assert result.retryable is retryable


def test_real_client_classifies_timeout() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow")

    client = CtsCountClient(config(), transport=httpx.MockTransport(handler))

    result = client.count("python")

    assert result.status == "timeout"
    assert result.error_code == "timeout"
    assert result.retryable is True


def test_real_client_classifies_network_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.NetworkError("network down")

    client = CtsCountClient(config(), transport=httpx.MockTransport(handler))

    result = client.count("python")

    assert result.status == "network_error"
    assert result.error_code == "network_error"
    assert result.retryable is True


def test_real_client_classifies_invalid_response_shape() -> None:
    client = CtsCountClient(
        config(),
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={})
        ),
    )

    result = client.count("python")

    assert result.status == "invalid_response"
    assert result.error_code == "invalid_response"
    assert result.retryable is False


def test_real_client_repr_redacts_tenant_secret() -> None:
    cfg = config()
    client = CtsCountClient(
        cfg, transport=httpx.MockTransport(lambda _request: httpx.Response(200))
    )

    assert "super-secret" not in repr(cfg)
    assert "super-secret" not in repr(client)
    assert "tenant_secret='***REDACTED***'" in repr(cfg)
