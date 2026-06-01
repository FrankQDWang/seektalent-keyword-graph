from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from seektalent_keyword_graph.cts.config import CtsClientConfig


@dataclass(frozen=True)
class CtsCountRequest:
    query_text: str
    query_mode: str = "keyword"


@dataclass(frozen=True)
class CtsCountResult:
    status: str
    total: int | None = None
    error_code: str | None = None
    retryable: bool = False
    latency_ms: int | None = None


class CtsCountClient:
    def __init__(
        self,
        config: CtsClientConfig,
        *,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout_seconds),
            transport=transport,
        )

    def count(self, query_text: str, query_mode: str = "keyword") -> CtsCountResult:
        payload = {
            "query": query_text,
            "queryMode": query_mode,
            "page": 1,
            "pageSize": 1,
        }
        headers = {
            "x-tenant-key": self._config.tenant_key,
            "x-tenant-secret": self._config.tenant_secret,
        }
        if self._config.trace_id:
            headers["x-trace-id"] = self._config.trace_id

        started = time.perf_counter()
        try:
            response = self._client.post(
                self._path(),
                json=payload,
                headers=headers,
                timeout=self._config.timeout_seconds,
            )
        except httpx.TimeoutException:
            return _error("timeout", "timeout", True, started)
        except httpx.NetworkError:
            return _error("network_error", "network_error", True, started)
        except httpx.TransportError:
            return _error("network_error", "network_error", True, started)

        return self._parse_response(response, started)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> CtsCountClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"CtsCountClient(config={self._config!r})"

    def _path(self) -> str:
        return f"/{self._config.api_version}/candidates/search"

    def _parse_response(
        self, response: httpx.Response, started: float
    ) -> CtsCountResult:
        if response.status_code in {401, 403}:
            return _error("auth_error", "auth_error", False, started)
        if response.status_code == 400:
            return _error("invalid_query", "invalid_query", False, started)
        if response.status_code == 429:
            return _error("rate_limited", "http_429", True, started)
        if 500 <= response.status_code <= 599:
            return _error("server_error", "http_5xx", True, started)
        if not 200 <= response.status_code <= 299:
            return _error("invalid_response", "invalid_response", False, started)

        try:
            body = response.json()
        except ValueError:
            return _error("invalid_response", "invalid_response", False, started)

        total = body.get("data", {}).get("total") if isinstance(body, dict) else None
        if isinstance(total, bool) or not isinstance(total, int):
            return _error("invalid_response", "invalid_response", False, started)

        return CtsCountResult(status="ok", total=total, latency_ms=_latency_ms(started))


def _error(
    status: str, error_code: str, retryable: bool, started: float
) -> CtsCountResult:
    return CtsCountResult(
        status=status,
        error_code=error_code,
        retryable=retryable,
        latency_ms=_latency_ms(started),
    )


def _latency_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
