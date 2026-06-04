"""Provider-aware recall policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

RecallBucket = Literal["healthy", "too_wide", "too_narrow", "zero", "stale", "unknown"]
RecallAction = Literal[
    "keep",
    "downrank",
    "replace",
    "add_alias_probe",
    "add_precision_companion",
    "score_only",
    "fallback",
]


@dataclass(frozen=True)
class ProviderRecallPolicy:
    """Thresholds for provider-specific recall interpretation."""

    healthy_min_total: int = 10
    healthy_max_total: int = 1000
    max_observation_age_days: int | None = None


DEFAULT_PROVIDER_RECALL_POLICY = ProviderRecallPolicy()


def recall_bucket_for_observation(
    *,
    total: int | None,
    status: str,
    observed_at: str | None = None,
    reference_time: str | None = None,
    policy: ProviderRecallPolicy = DEFAULT_PROVIDER_RECALL_POLICY,
) -> RecallBucket:
    """Classify one provider observation without calling the provider."""

    if status != "ok" or total is None:
        return "unknown"
    if (
        observed_at is not None
        and reference_time is not None
        and policy.max_observation_age_days is not None
        and _is_stale(observed_at, reference_time, policy.max_observation_age_days)
    ):
        return "stale"
    if total == 0:
        return "zero"
    if total < policy.healthy_min_total:
        return "too_narrow"
    if total > policy.healthy_max_total:
        return "too_wide"
    return "healthy"


def recommended_action_for_bucket(bucket: str) -> RecallAction:
    """Return the default term-pool action for a recall bucket."""

    if bucket == "healthy":
        return "keep"
    if bucket == "too_wide":
        return "add_precision_companion"
    if bucket in {"too_narrow", "zero"}:
        return "replace"
    if bucket in {"stale", "unknown"}:
        return "score_only"
    return "fallback"


def _is_stale(observed_at: str, reference_time: str, max_age_days: int) -> bool:
    observed = _parse_instant(observed_at)
    reference = _parse_instant(reference_time)
    return observed < reference - timedelta(days=max_age_days)


def _parse_instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
