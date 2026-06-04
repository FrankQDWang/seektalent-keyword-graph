from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CtsClientConfig:
    base_url: str
    tenant_key: str
    tenant_secret: str
    timeout_seconds: float = 5.0
    api_version: str = "v1"
    trace_id: str | None = None

    @classmethod
    def from_env(cls) -> CtsClientConfig:
        return cls(
            base_url=_required_env("KEYWORD_GRAPH_CTS_BASE_URL"),
            tenant_key=_required_env("KEYWORD_GRAPH_CTS_TENANT_KEY"),
            tenant_secret=_required_env("KEYWORD_GRAPH_CTS_TENANT_SECRET"),
            timeout_seconds=float(os.getenv("KEYWORD_GRAPH_CTS_TIMEOUT_SECONDS", "5")),
            api_version=os.getenv("KEYWORD_GRAPH_CTS_API_VERSION", "v1"),
            trace_id=os.getenv("KEYWORD_GRAPH_CTS_TRACE_ID") or None,
        )

    def __repr__(self) -> str:
        return (
            "CtsClientConfig("
            f"base_url={self.base_url!r}, "
            f"tenant_key={self.tenant_key!r}, "
            "tenant_secret='***REDACTED***', "
            f"timeout_seconds={self.timeout_seconds!r}, "
            f"api_version={self.api_version!r}, "
            f"trace_id={self.trace_id!r})"
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"missing required CTS environment variable: {name}")
    return value
