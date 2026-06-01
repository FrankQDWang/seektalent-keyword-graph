"""Deterministic scoring helpers for runtime query planning."""

from __future__ import annotations

from seektalent_keyword_graph.domain.policies import BUNDLE_TYPE_RANK

STRENGTH_RANK = {
    "required": 0,
    "preferred": 10,
    "nice_to_have": 20,
}


def bundle_sort_key(
    bundle_type: str,
    requirement_strength: str,
    source_order: int,
    label: str,
) -> tuple[int, int, int, str]:
    """Return the stable sort key used before max-bundle trimming."""
    return (
        BUNDLE_TYPE_RANK[bundle_type],
        STRENGTH_RANK.get(requirement_strength, 99),
        source_order,
        label.casefold(),
    )


def warning_sort_key(code: str, first_source_order: int) -> tuple[int, int, str]:
    """Return a stable warning sort key without importing runtime models."""
    from seektalent_keyword_graph.domain.policies import WARNING_RANK

    return (WARNING_RANK.get(code, 99), first_source_order, code)
