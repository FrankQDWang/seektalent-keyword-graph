from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.cts.fake_client import FakeCtsClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "cts" / "fake_totals.json"


def test_fake_client_returns_success_and_records_request() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("python", query_mode="keyword")

    assert result.total == 42
    assert result.status == "ok"
    assert result.retryable is False
    assert client.requests[0].query_text == "python"
    assert client.requests[0].query_mode == "keyword"


def test_fake_client_returns_zero_recall() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("no recall")

    assert result.total == 0
    assert result.status == "ok"


def test_fake_client_simulates_timeout() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("slow query")

    assert result.total is None
    assert result.status == "timeout"
    assert result.error_code == "timeout"
    assert result.retryable is True


def test_fake_client_simulates_429() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("rate limited")

    assert result.status == "rate_limited"
    assert result.error_code == "http_429"
    assert result.retryable is True


def test_fake_client_simulates_5xx() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("server unhappy")

    assert result.status == "server_error"
    assert result.error_code == "http_5xx"
    assert result.retryable is True


def test_fake_client_simulates_auth_error() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("bad credentials")

    assert result.status == "auth_error"
    assert result.error_code == "auth_error"
    assert result.retryable is False


def test_fake_client_simulates_network_error() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("network down")

    assert result.status == "network_error"
    assert result.error_code == "network_error"
    assert result.retryable is True


def test_fake_client_unknown_query_returns_zero_without_fixed_branches() -> None:
    client = FakeCtsClient.from_json(FIXTURE)

    result = client.count("not in fixture")

    assert result.total == 0
    assert result.status == "ok"
    assert client.requests[-1].query_text == "not in fixture"
