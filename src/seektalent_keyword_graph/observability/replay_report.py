"""Deterministic replay evaluation summaries."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_replay_report(
    *,
    plan_responses: list[Any],
    recall_responses: list[Any],
    provider_recall_summary: dict[str, dict[str, int]],
) -> dict[str, object]:
    """Summarize query-plan and query-recall replay responses."""

    bundle_counts: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    rejected_counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    observation_status_counts: Counter[str] = Counter()
    cases: list[dict[str, object]] = []

    for response in sorted(plan_responses, key=lambda item: item.request_id):
        case_bundle_counts = Counter(
            bundle.bundle_type for bundle in response.query_bundles
        )
        case_warning_counts = Counter(warning.code for warning in response.warnings)
        case_rejected_counts = Counter(
            rejection.reason_code for rejection in response.rejected_surfaces
        )
        bundle_counts.update(case_bundle_counts)
        warning_counts.update(case_warning_counts)
        rejected_counts.update(case_rejected_counts)
        cases.append(
            {
                "case_id": response.request_id,
                "case_type": "query_plan",
                "bundle_type_counts": dict(sorted(case_bundle_counts.items())),
                "warning_counts": dict(sorted(case_warning_counts.items())),
                "rejected_reason_counts": dict(sorted(case_rejected_counts.items())),
                "lineage": response.lineage.model_dump(mode="json"),
            }
        )

    for response in sorted(recall_responses, key=lambda item: item.request_id):
        case_warning_counts = Counter(warning.code for warning in response.warnings)
        case_action_counts = Counter(
            recommendation.action for recommendation in response.recommendations
        )
        case_status_counts = Counter(
            observation.status for observation in response.input_observations
        )
        warning_counts.update(case_warning_counts)
        action_counts.update(case_action_counts)
        observation_status_counts.update(case_status_counts)
        cases.append(
            {
                "case_id": response.request_id,
                "case_type": "query_recall",
                "provider": response.provider,
                "warning_counts": dict(sorted(case_warning_counts.items())),
                "query_recall_action_counts": dict(sorted(case_action_counts.items())),
                "provider_observation_status_counts": dict(
                    sorted(case_status_counts.items())
                ),
                "lineage": response.lineage.model_dump(mode="json"),
            }
        )

    cases = sorted(cases, key=lambda item: str(item["case_id"]))
    stable_case_ids = [str(case["case_id"]) for case in cases]

    return {
        "schema_version": "replay-report-v1",
        "summary": {
            "case_count": len(cases),
            "bundle_type_counts": dict(sorted(bundle_counts.items())),
            "warning_counts": dict(sorted(warning_counts.items())),
            "rejected_reason_counts": dict(sorted(rejected_counts.items())),
            "query_recall_action_counts": dict(sorted(action_counts.items())),
            "provider_observation_status_counts": dict(
                sorted(observation_status_counts.items())
            ),
        },
        "provider_recall_summary": _sorted_nested(provider_recall_summary),
        "term_pool_action_summary": dict(sorted(action_counts.items())),
        "cases": cases,
        "stability": {
            "deterministic_order": True,
            "stable_case_ids": stable_case_ids,
        },
    }


def _sorted_nested(payload: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    return {
        key: dict(sorted(value.items()))
        for key, value in sorted(payload.items())
    }
