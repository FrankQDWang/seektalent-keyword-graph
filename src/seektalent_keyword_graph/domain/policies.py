"""Runtime query planning policy constants."""

from __future__ import annotations

SELECTION_POLICY_VERSION = "policy-v1"

ANCHOR_RECALL_BUCKETS = frozenset({"healthy"})
ALIAS_PROBE_RECALL_BUCKETS = frozenset({"zero", "too_narrow", "stale"})
EXPLORATION_RECALL_BUCKETS = frozenset({"unknown"})

BUNDLE_TYPE_RANK = {
    "anchor": 10,
    "precision": 20,
    "alias_probe": 30,
    "exploration": 40,
    "fallback": 90,
}

WARNING_RANK = {
    "no_match": 10,
    "stale_observation": 20,
    "unknown_observation": 30,
    "fallback": 40,
    "partial_snapshot": 50,
}

REJECTION_REASON_RANK = {
    "company_like": 10,
    "department_like": 20,
    "too_generic": 30,
    "zero_recall": 40,
    "too_wide_without_companion": 50,
    "stale_observation": 60,
    "low_confidence_alias": 70,
    "policy_blocked": 80,
    "no_active_concept": 90,
}
