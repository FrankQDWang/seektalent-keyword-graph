from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from seektalent_keyword_graph.cts.count_client import CtsCountResult


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds must be non-negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")


def retry_count(
    operation: Callable[[], CtsCountResult], policy: RetryPolicy | None = None
) -> CtsCountResult:
    effective_policy = policy or RetryPolicy()
    delay = effective_policy.initial_delay_seconds
    result = operation()

    for _attempt in range(1, effective_policy.max_attempts):
        if not result.retryable:
            return result
        if delay:
            time.sleep(delay)
        delay *= effective_policy.backoff_multiplier
        result = operation()

    return result
