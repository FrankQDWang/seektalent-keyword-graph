from __future__ import annotations


def recall_bucket(total: int | None) -> str:
    if total is None:
        return "unknown"
    if total == 0:
        return "zero"
    if total > 200000:
        return "too_wide"
    if total < 100:
        return "too_narrow"
    return "healthy"
