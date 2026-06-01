from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from seektalent_keyword_graph.contracts import (
    OptimizedQueryTerm,
    QueryRecallAlternative,
    QueryRecallLineage,
    QueryRecallObservation,
    QueryRecallRecommendation,
    QueryRecallRequest,
    QueryRecallRequestTerm,
    QueryRecallResponse,
    QueryRecallWarning,
)

CONTRACT_DIR = Path("contracts/query-recall")


def _response_payload() -> dict[str, object]:
    return {
        "schema_version": "query-recall-response-v1",
        "request_id": "req-123",
        "provider": "liepin",
        "kg_snapshot_id": "kg-2026-06-01",
        "selection_policy_version": "policy-v1",
        "input_observations": [
            {
                "provider": "liepin",
                "surface_id": "surface-k8s",
                "query_text": "k8s",
                "query_hash": "sha256:k8s",
                "query_mode": "keyword",
                "total": 0,
                "latency_ms": 12,
                "status": "ok",
                "error_code": None,
                "observed_at": "2026-06-01T00:00:00Z",
                "recall_bucket": "zero",
                "provider_api_version": "liepin-v1",
                "evidence_ref": "probe:obs-k8s",
            }
        ],
        "alternatives": [
            {
                "query_text": "Kubernetes",
                "surface_id": "surface-kubernetes",
                "query_mode": "keyword",
                "relation_type": "alias",
                "confidence": 0.94,
                "source_concept_id": "concept-kubernetes",
                "source_surface_id": "surface-k8s",
                "target_surface_id": "surface-kubernetes",
                "evidence_type": "curated_alias",
                "evidence_ref": "relation:alias-k8s-kubernetes",
                "observation": {
                    "provider": "liepin",
                    "surface_id": "surface-kubernetes",
                    "query_text": "Kubernetes",
                    "query_hash": "sha256:kubernetes",
                    "query_mode": "keyword",
                    "total": 42,
                    "latency_ms": 20,
                    "status": "ok",
                    "error_code": None,
                    "observed_at": "2026-06-01T00:00:00Z",
                    "recall_bucket": "healthy",
                    "provider_api_version": "liepin-v1",
                    "evidence_ref": "probe:obs-kubernetes",
                },
            }
        ],
        "recommendations": [
            {
                "action": "replace",
                "query_text": "k8s",
                "recommended_query_text": "Kubernetes",
                "reason_code": "zero_recall",
                "reason": "Original term has zero recall and alias has healthy recall.",
                "provider": "liepin",
                "evidence_observation_ids": ["probe:obs-k8s", "probe:obs-kubernetes"],
            }
        ],
        "warnings": [
            {
                "code": "zero_recall",
                "message": "Input term has zero observed recall.",
                "query_text": "k8s",
                "provider": "liepin",
            }
        ],
        "optimized_terms": [
            {
                "query_text": "Kubernetes",
                "query_mode": "keyword",
                "action": "replace",
                "rank": 1,
                "source_query_text": "k8s",
                "provider": "liepin",
                "recall_bucket": "healthy",
                "reason": "Alias has healthier provider recall.",
            }
        ],
        "lineage": {
            "input_hash": "sha256:input",
            "snapshot_schema_version": "snapshot-v1",
            "selection_policy_version": "policy-v1",
            "provider_sources": ["liepin", "cts"],
            "source_refs": ["snapshot:kg-2026-06-01"],
        },
    }


def test_request_accepts_query_text_or_terms_and_requires_non_blank_input() -> None:
    query_text_request = QueryRecallRequest.model_validate(
        {"request_id": "req-text", "provider": "cts", "query_text": "Python"}
    )
    terms_request = QueryRecallRequest.model_validate(
        {
            "request_id": "req-terms",
            "provider": "boss",
            "query_terms": [{"text": "Kubernetes", "strength": "required"}],
        }
    )

    assert query_text_request.schema_version == "query-recall-request-v1"
    assert query_text_request.provider == "cts"
    assert terms_request.provider == "boss"
    assert terms_request.query_terms == [
        QueryRecallRequestTerm(text="Kubernetes", strength="required")
    ]

    with pytest.raises(ValidationError):
        QueryRecallRequest.model_validate(
            {"request_id": "req-empty", "provider": "cts", "query_terms": []}
        )
    with pytest.raises(ValidationError):
        QueryRecallRequest.model_validate(
            {"request_id": "req-blank", "provider": "cts", "query_text": " \n"}
        )


@pytest.mark.parametrize("provider", ["cts", "liepin", "boss"])
def test_provider_is_required_but_not_cts_only(provider: str) -> None:
    request = QueryRecallRequest.model_validate(
        {"request_id": "req-provider", "provider": provider, "query_text": "SQL"}
    )

    assert request.provider == provider

    with pytest.raises(ValidationError):
        QueryRecallRequest.model_validate(
            {"request_id": "req-provider", "query_text": "SQL"}
        )


def test_nested_response_models_validate_public_contract() -> None:
    response = QueryRecallResponse.model_validate(_response_payload())

    assert response.input_observations[0] == QueryRecallObservation(
        provider="liepin",
        surface_id="surface-k8s",
        query_text="k8s",
        query_hash="sha256:k8s",
        query_mode="keyword",
        total=0,
        latency_ms=12,
        status="ok",
        error_code=None,
        observed_at="2026-06-01T00:00:00Z",
        recall_bucket="zero",
        provider_api_version="liepin-v1",
        evidence_ref="probe:obs-k8s",
    )
    assert isinstance(response.alternatives[0], QueryRecallAlternative)
    assert isinstance(response.recommendations[0], QueryRecallRecommendation)
    assert isinstance(response.warnings[0], QueryRecallWarning)
    assert response.optimized_terms == [
        OptimizedQueryTerm(
            query_text="Kubernetes",
            query_mode="keyword",
            action="replace",
            rank=1,
            source_query_text="k8s",
            provider="liepin",
            recall_bucket="healthy",
            reason="Alias has healthier provider recall.",
        )
    ]
    assert response.lineage == QueryRecallLineage(
        input_hash="sha256:input",
        snapshot_schema_version="snapshot-v1",
        selection_policy_version="policy-v1",
        provider_sources=["liepin", "cts"],
        source_refs=["snapshot:kg-2026-06-01"],
    )


def test_query_recall_examples_validate_through_pydantic() -> None:
    request = json.loads((CONTRACT_DIR / "request.example.json").read_text())
    response = json.loads((CONTRACT_DIR / "response.example.json").read_text())

    parsed_request = QueryRecallRequest.model_validate(request)
    parsed_response = QueryRecallResponse.model_validate(response)

    assert parsed_request.provider in {"cts", "liepin", "boss"}
    assert parsed_response.input_observations[0].provider == parsed_request.provider
    assert parsed_response.input_observations[0].provider_api_version
    assert "query_bundles" not in response


def _canonical_schema(model: type[QueryRecallRequest | QueryRecallResponse]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def test_generated_request_schema_matches_committed_file_byte_for_byte() -> None:
    expected = (CONTRACT_DIR / "query-recall-request.schema.json").read_text()

    assert _canonical_schema(QueryRecallRequest) == expected


def test_generated_response_schema_matches_committed_file_byte_for_byte() -> None:
    expected = (CONTRACT_DIR / "query-recall-response.schema.json").read_text()

    assert _canonical_schema(QueryRecallResponse) == expected
