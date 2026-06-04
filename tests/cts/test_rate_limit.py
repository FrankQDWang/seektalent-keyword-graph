from __future__ import annotations

import asyncio

from seektalent_keyword_graph.cts.rate_limit import (
    CtsProbeRateLimitConfig,
    CtsProbeThrottler,
)


def test_default_rate_limit_is_one_rps_and_single_concurrency() -> None:
    config = CtsProbeRateLimitConfig()

    assert config.requests_per_second == 1.0
    assert config.concurrency == 1


def test_async_throttler_never_exceeds_configured_concurrency() -> None:
    async def run_operations() -> int:
        throttler = CtsProbeThrottler(
            CtsProbeRateLimitConfig(requests_per_second=1000.0, concurrency=2)
        )
        active = 0
        max_active = 0

        async def operation() -> None:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.01)
            active -= 1

        await asyncio.gather(*(throttler.run(operation) for _ in range(8)))
        return max_active

    assert asyncio.run(run_operations()) == 2
