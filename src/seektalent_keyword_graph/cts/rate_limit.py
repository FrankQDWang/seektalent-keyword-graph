from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class CtsProbeRateLimitConfig:
    requests_per_second: float = 1.0
    concurrency: int = 1

    def __post_init__(self) -> None:
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")


class CtsProbeThrottler:
    def __init__(self, config: CtsProbeRateLimitConfig | None = None) -> None:
        self.config = config or CtsProbeRateLimitConfig()
        self._semaphore = asyncio.Semaphore(self.config.concurrency)
        self._rate_lock = asyncio.Lock()
        self._next_start = 0.0

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            await self._wait_for_token()
            return await operation()

    async def _wait_for_token(self) -> None:
        interval = 1.0 / self.config.requests_per_second
        async with self._rate_lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_start - now)
            if wait_seconds:
                await asyncio.sleep(wait_seconds)
                now = time.monotonic()
            self._next_start = max(now, self._next_start) + interval
