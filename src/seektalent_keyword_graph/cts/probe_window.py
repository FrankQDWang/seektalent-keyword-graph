from __future__ import annotations

from datetime import time


def is_within_probe_window(now: time, start: time, end: time) -> bool:
    return start <= now < end


def can_run_real_probe(dry_run: bool, now: time, start: time, end: time) -> bool:
    return dry_run or is_within_probe_window(now, start, end)
