from __future__ import annotations

from seektalent_keyword_graph.cts.count_client import CtsCountResult
from seektalent_keyword_graph.cts.retry import RetryPolicy, retry_count


def test_retry_policy_retries_retryable_errors_until_success() -> None:
    attempts = [
        CtsCountResult(status="timeout", error_code="timeout", retryable=True),
        CtsCountResult(status="rate_limited", error_code="http_429", retryable=True),
        CtsCountResult(status="ok", total=9),
    ]
    seen: list[int] = []

    def operation() -> CtsCountResult:
        seen.append(1)
        return attempts.pop(0)

    result = retry_count(
        operation, RetryPolicy(max_attempts=3, initial_delay_seconds=0)
    )

    assert result.total == 9
    assert result.status == "ok"
    assert len(seen) == 3


def test_retry_policy_stops_on_non_retryable_error() -> None:
    attempts = [
        CtsCountResult(status="auth_error", error_code="auth_error", retryable=False),
        CtsCountResult(status="ok", total=9),
    ]

    result = retry_count(
        lambda: attempts.pop(0), RetryPolicy(max_attempts=3, initial_delay_seconds=0)
    )

    assert result.status == "auth_error"
    assert len(attempts) == 1


def test_retry_policy_returns_last_retryable_error_after_attempts_exhausted() -> None:
    attempts = [
        CtsCountResult(status="server_error", error_code="http_5xx", retryable=True),
        CtsCountResult(
            status="network_error", error_code="network_error", retryable=True
        ),
    ]

    result = retry_count(
        lambda: attempts.pop(0), RetryPolicy(max_attempts=2, initial_delay_seconds=0)
    )

    assert result.status == "network_error"
    assert result.error_code == "network_error"
    assert attempts == []
