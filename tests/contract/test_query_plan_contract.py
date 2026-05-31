from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from seektalent_keyword_graph.contracts import (
    ConceptSheetRow,
    QueryBundle,
    QueryPlanQuery,
    QueryPlanRequest,
    QueryPlanResponse,
    QueryPlanWarning,
    RejectedSurface,
    RequirementTerm,
)

CONTRACT_DIR = Path("contracts/query-plan")
BUNDLE_TYPES = ("anchor", "precision", "alias_probe", "exploration", "fallback")
CONCEPT_TYPES = (
    "skill",
    "platform",
    "language",
    "framework",
    "tool",
    "domain",
    "certificate",
    "method",
    "job_keyword",
    "qualification",
    "unknown",
)


def _response_payload() -> dict[str, object]:
    return {
        "schema_version": "query-plan-response-v1",
        "request_id": "req-123",
        "kg_snapshot_id": "kg-2026-05-31",
        "selection_policy_version": "policy-v1",
        "concept_sheet": [
            {
                "concept_id": "concept-kubernetes",
                "canonical_label": "Kubernetes",
                "concept_type": "platform",
                "requirement_strength": "required",
                "matched_terms": ["Kubernetes", "k8s"],
                "selected_surfaces": ["Kubernetes", "k8s"],
                "recall_bucket": "healthy",
                "confidence": 0.96,
            }
        ],
        "query_bundles": [
            {
                "bundle_type": "anchor",
                "label": "Kubernetes anchor",
                "queries": [
                    {
                        "query_text": '"Kubernetes"',
                        "query_mode": "exact",
                        "surfaces": ["Kubernetes"],
                        "reason": "High-confidence required concept.",
                        "priority": 1,
                        "source_concept_ids": ["concept-kubernetes"],
                        "recall_bucket": "healthy",
                    }
                ],
                "rationale": "Required concept with healthy observed recall.",
                "priority": 1,
                "source_concept_ids": ["concept-kubernetes"],
            }
        ],
        "rejected_surfaces": [
            {
                "surface_text": "Acme Cloud",
                "normalized_surface": "acme cloud",
                "reason_code": "company_like",
                "source": "jd_text",
                "evidence": "Acme Cloud platform experience.",
            }
        ],
        "warnings": [
            {
                "code": "fallback",
                "message": "Fallback bundle included for uncovered terms.",
                "source_terms": ["distributed systems"],
            }
        ],
        "lineage": {
            "input_hash": "sha256:6a9f5d4b8c7e",
            "snapshot_schema_version": "snapshot-v1",
            "selection_policy_version": "policy-v1",
            "source_refs": ["jd:demo-001", "snapshot:kg-2026-05-31"],
        },
    }


def test_request_defaults_and_enum_validation() -> None:
    request = QueryPlanRequest.model_validate(
        {
            "request_id": "req-123",
            "requirement_terms": [{"text": "Kubernetes"}],
        }
    )

    assert request.schema_version == "query-plan-request-v1"
    assert request.max_query_bundles == 5
    assert request.include_exploration is True
    assert request.requirement_terms == [
        RequirementTerm(text="Kubernetes", strength="required", source="requirement")
    ]

    with pytest.raises(ValidationError):
        QueryPlanRequest.model_validate(
            {
                "request_id": "req-123",
                "requirement_terms": [{"text": "Kubernetes", "strength": "mandatory"}],
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "req-123", "requirement_terms": []},
        {
            "request_id": "req-123",
            "requirement_terms": [],
            "title": "   ",
            "jd_text": "\t",
            "notes": [" ", "\n"],
        },
    ],
)
def test_request_requires_at_least_one_non_blank_input_source(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        QueryPlanRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"request_id": "req-title", "requirement_terms": [], "title": "Backend Lead"},
        {"request_id": "req-jd", "requirement_terms": [], "jd_text": "Build APIs."},
        {"request_id": "req-notes", "requirement_terms": [], "notes": ["GraphQL"]},
    ],
)
def test_request_allows_title_jd_or_notes_only_inputs(
    payload: dict[str, object],
) -> None:
    request = QueryPlanRequest.model_validate(payload)

    assert request.request_id == payload["request_id"]


def test_nested_response_models_validate_public_contract() -> None:
    response = QueryPlanResponse.model_validate(_response_payload())

    assert response.concept_sheet == [
        ConceptSheetRow(
            concept_id="concept-kubernetes",
            canonical_label="Kubernetes",
            concept_type="platform",
            requirement_strength="required",
            matched_terms=["Kubernetes", "k8s"],
            selected_surfaces=["Kubernetes", "k8s"],
            recall_bucket="healthy",
            confidence=0.96,
        )
    ]
    assert response.query_bundles[0].queries[0].query_mode == "exact"
    assert response.rejected_surfaces == [
        RejectedSurface(
            surface_text="Acme Cloud",
            normalized_surface="acme cloud",
            reason_code="company_like",
            source="jd_text",
            evidence="Acme Cloud platform experience.",
        )
    ]
    assert response.warnings == [
        QueryPlanWarning(
            code="fallback",
            message="Fallback bundle included for uncovered terms.",
            source_terms=["distributed systems"],
        )
    ]
    assert response.lineage.snapshot_schema_version == "snapshot-v1"


@pytest.mark.parametrize("concept_type", CONCEPT_TYPES)
def test_all_planned_concept_type_enum_values_are_accepted(concept_type: str) -> None:
    row = ConceptSheetRow.model_validate(
        {
            **_response_payload()["concept_sheet"][0],
            "concept_type": concept_type,
        }
    )

    assert row.concept_type == concept_type


@pytest.mark.parametrize("bundle_type", BUNDLE_TYPES)
def test_all_bundle_type_enum_values_are_accepted(bundle_type: str) -> None:
    bundle = QueryBundle.model_validate(
        {
            "bundle_type": bundle_type,
            "label": f"{bundle_type} bundle",
            "queries": [
                {
                    "query_text": bundle_type,
                    "query_mode": "keyword",
                    "surfaces": [bundle_type],
                    "reason": "contract coverage",
                    "priority": 1,
                    "source_concept_ids": [],
                    "recall_bucket": "unknown",
                }
            ],
            "rationale": "contract coverage",
            "priority": 1,
            "source_concept_ids": [],
        }
    )

    assert bundle.bundle_type == bundle_type


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (
            ConceptSheetRow,
            _response_payload()["concept_sheet"][0],
            "matched_terms",
        ),
        (
            ConceptSheetRow,
            _response_payload()["concept_sheet"][0],
            "selected_surfaces",
        ),
        (
            QueryPlanQuery,
            _response_payload()["query_bundles"][0]["queries"][0],
            "surfaces",
        ),
    ],
)
def test_support_lists_reject_empty_values(
    model: type, payload: dict[str, object], field: str
) -> None:
    payload_with_empty_list = dict(payload)
    payload_with_empty_list[field] = []

    with pytest.raises(ValidationError):
        model.model_validate(payload_with_empty_list)


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (RequirementTerm, {"text": "Kubernetes"}, "text"),
        (QueryPlanRequest, {"request_id": "req-123", "title": "Backend"}, "request_id"),
        (ConceptSheetRow, _response_payload()["concept_sheet"][0], "canonical_label"),
        (
            QueryPlanQuery,
            _response_payload()["query_bundles"][0]["queries"][0],
            "query_text",
        ),
        (QueryPlanWarning, _response_payload()["warnings"][0], "message"),
    ],
)
def test_representative_non_empty_strings_reject_whitespace_only_values(
    model: type, payload: dict[str, object], field: str
) -> None:
    payload_with_blank = dict(payload)
    payload_with_blank[field] = " \t\n"

    with pytest.raises(ValidationError):
        model.model_validate(payload_with_blank)


def test_support_lists_reject_whitespace_only_items() -> None:
    payload = dict(_response_payload()["query_bundles"][0]["queries"][0])
    payload["surfaces"] = [" \t\n"]

    with pytest.raises(ValidationError):
        QueryPlanQuery.model_validate(payload)


def test_query_plan_examples_validate_through_pydantic() -> None:
    request = json.loads((CONTRACT_DIR / "request.example.json").read_text())
    response = json.loads((CONTRACT_DIR / "response.example.json").read_text())

    QueryPlanRequest.model_validate(request)
    parsed_response = QueryPlanResponse.model_validate(response)

    bundle_types = {bundle.bundle_type for bundle in parsed_response.query_bundles}
    assert bundle_types == set(BUNDLE_TYPES)
    assert any(
        surface.reason_code == "company_like"
        for surface in parsed_response.rejected_surfaces
    )


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (
            QueryPlanRequest,
            {"request_id": "req-123", "requirement_terms": []},
            "request_id",
        ),
        (QueryPlanResponse, _response_payload(), "lineage"),
        (ConceptSheetRow, _response_payload()["concept_sheet"][0], "concept_id"),
        (QueryBundle, _response_payload()["query_bundles"][0], "queries"),
        (RejectedSurface, _response_payload()["rejected_surfaces"][0], "reason_code"),
    ],
)
def test_removing_required_public_fields_fails_validation(
    model: type, payload: dict[str, object], field: str
) -> None:
    payload_without_field = dict(payload)
    payload_without_field.pop(field)

    with pytest.raises(ValidationError):
        model.model_validate(payload_without_field)
