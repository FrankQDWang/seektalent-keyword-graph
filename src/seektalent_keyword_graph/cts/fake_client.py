from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.cts.count_client import CtsCountRequest, CtsCountResult

_ERRORS: dict[str, tuple[str, str, bool]] = {
    "timeout": ("timeout", "timeout", True),
    "rate_limited": ("rate_limited", "http_429", True),
    "server_error": ("server_error", "http_5xx", True),
    "auth_error": ("auth_error", "auth_error", False),
    "network_error": ("network_error", "network_error", True),
    "invalid_query": ("invalid_query", "invalid_query", False),
    "invalid_response": ("invalid_response", "invalid_response", False),
}


class FakeCtsClient:
    def __init__(self, responses: dict[str, CtsCountResult]) -> None:
        self._responses = responses
        self.requests: list[CtsCountRequest] = []

    @classmethod
    def from_json(cls, path: str | Path) -> FakeCtsClient:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        queries = raw.get("queries")
        if not isinstance(queries, dict):
            raise ValueError("fake CTS fixture must contain a queries object")

        responses = {
            query_text: _parse_fixture_result(query_text, value)
            for query_text, value in queries.items()
        }
        return cls(responses)

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        self.requests.append(CtsCountRequest(query_text, query_mode))
        return self._responses.get(query_text, CtsCountResult(status="ok", total=0))


def _parse_fixture_result(query_text: str, value: Any) -> CtsCountResult:
    if not isinstance(value, dict):
        raise ValueError(f"fake CTS fixture for {query_text!r} must be an object")

    status = value.get("status")
    if status is None:
        total = value.get("total")
        if isinstance(total, bool) or not isinstance(total, int):
            raise ValueError(f"fake CTS fixture for {query_text!r} needs integer total")
        return CtsCountResult(status="ok", total=total)

    if status not in _ERRORS:
        raise ValueError(f"unsupported fake CTS status for {query_text!r}: {status!r}")
    result_status, error_code, retryable = _ERRORS[status]
    return CtsCountResult(
        status=result_status, error_code=error_code, retryable=retryable
    )
