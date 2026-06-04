"""Builder-only CTS count clients."""

from __future__ import annotations

__all__ = [
    "CtsClientConfig",
    "CtsCountClient",
    "CtsCountRequest",
    "CtsCountResult",
    "FakeCtsClient",
    "CtsProbeRateLimitConfig",
    "CtsProbeThrottler",
    "ProbeWindowConfig",
    "REAL_CTS_GATE_TOKEN",
    "RealProbeGateError",
    "RetryPolicy",
    "ensure_real_probe_allowed",
    "is_inside_probe_window",
    "retry_count",
    "validate_real_probe_gate",
]

from seektalent_keyword_graph.cts.config import CtsClientConfig
from seektalent_keyword_graph.cts.count_client import (
    CtsCountClient,
    CtsCountRequest,
    CtsCountResult,
)
from seektalent_keyword_graph.cts.fake_client import FakeCtsClient
from seektalent_keyword_graph.cts.probe_window import (
    REAL_CTS_GATE_TOKEN,
    ProbeWindowConfig,
    RealProbeGateError,
    ensure_real_probe_allowed,
    is_inside_probe_window,
    validate_real_probe_gate,
)
from seektalent_keyword_graph.cts.rate_limit import (
    CtsProbeRateLimitConfig,
    CtsProbeThrottler,
)
from seektalent_keyword_graph.cts.retry import RetryPolicy, retry_count
