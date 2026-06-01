from __future__ import annotations

import pytest

from seektalent_keyword_graph.contracts import (
    QueryRecallRequest,
    QueryRecallRequestTerm,
)
from seektalent_keyword_graph.engine import KeywordGraph
from seektalent_keyword_graph.runtime.errors import KeywordGraphRuntimeError
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore


def test_analyze_query_recall_returns_provider_observation_and_keep_term(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    response = KeywordGraph(snapshot_store).analyze_query_recall(
        QueryRecallRequest(
            request_id="req-python",
            provider="cts",
            query_text="Python",
        )
    )

    assert response.schema_version == "query-recall-response-v1"
    assert response.provider == "cts"
    assert response.kg_snapshot_id == "kg-test-snapshot"
    assert response.selection_policy_version == "policy-v1"
    assert [
        (
            observation.provider,
            observation.surface_id,
            observation.total,
            observation.status,
            observation.recall_bucket,
        )
        for observation in response.input_observations
    ] == [("cts", "surface:python", 42, "ok", "healthy")]
    assert [
        (item.query_text, item.action, item.recall_bucket)
        for item in response.optimized_terms
    ] == [("Python", "keep", "healthy")]
    assert response.recommendations[0].action == "keep"
    assert response.recommendations[0].evidence_observation_ids == [
        response.input_observations[0].observation_id
    ]
    assert response.warnings == []
    assert response.lineage.provider_sources == ["cts", "liepin"]
    assert response.lineage.source_refs[:3] == [
        "request:req-python",
        "snapshot:kg-test-snapshot",
        "provider:cts",
    ]


def test_optimize_query_terms_returns_deterministic_actions(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    request = QueryRecallRequest(
        request_id="req-pool",
        provider="cts",
        query_terms=[
            QueryRecallRequestTerm(text="React"),
            QueryRecallRequestTerm(text="Kubernetes"),
            QueryRecallRequestTerm(text="Kafka"),
            QueryRecallRequestTerm(text="LLMOps", strength="preferred"),
            QueryRecallRequestTerm(text="GraphQL", strength="preferred"),
        ],
        max_alternatives=10,
        max_precision_companions=3,
    )

    first = KeywordGraph(snapshot_store).optimize_query_terms(request)
    second = KeywordGraph(snapshot_store).optimize_query_terms(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert [(warning.code, warning.query_text) for warning in first.warnings] == [
        ("no_match", "GraphQL"),
        ("zero_recall", "React"),
        ("too_wide_recall", "Kubernetes"),
        ("stale_observation", "Kafka"),
        ("unknown_observation", "LLMOps"),
        ("fallback", "GraphQL"),
    ]
    assert [
        (
            recommendation.query_text,
            recommendation.action,
            recommendation.recommended_query_text,
        )
        for recommendation in first.recommendations
    ] == [
        ("React", "replace", "React.js"),
        ("Kubernetes", "add_precision_companion", "Docker"),
        ("Kafka", "replace", "Apache Kafka"),
        ("LLMOps", "score_only", None),
        ("GraphQL", "fallback", None),
    ]
    assert [
        (term.source_query_text, term.query_text, term.action, term.recall_bucket)
        for term in first.optimized_terms
    ] == [
        ("React", "React.js", "replace", "healthy"),
        ("Kubernetes", "Docker", "add_precision_companion", "healthy"),
        ("Kafka", "Apache Kafka", "replace", "healthy"),
        ("LLMOps", "LLMOps", "score_only", "unknown"),
        ("GraphQL", "GraphQL", "fallback", "unknown"),
    ]


def test_unsupported_provider_raises_typed_runtime_error(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    with pytest.raises(KeywordGraphRuntimeError, match="unsupported provider"):
        KeywordGraph(snapshot_store).analyze_query_recall(
            QueryRecallRequest(
                request_id="req-provider",
                provider="boss",
                query_text="Python",
            )
        )


def test_matched_unknown_observation_is_distinct_from_no_match(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    response = KeywordGraph(snapshot_store).optimize_query_terms(
        QueryRecallRequest(
            request_id="req-unknown-vs-no-match",
            provider="cts",
            query_terms=[
                QueryRecallRequestTerm(text="LLMOps"),
                QueryRecallRequestTerm(text="GraphQL"),
            ],
        )
    )

    warning_by_query = {
        warning.query_text: warning.code for warning in response.warnings
    }
    assert warning_by_query["LLMOps"] == "unknown_observation"
    assert warning_by_query["GraphQL"] == "fallback"
    assert [observation.surface_id for observation in response.input_observations] == [
        "surface:llmops"
    ]
    assert "concept:concept:llmops" in response.lineage.source_refs
    assert all("graphql" not in ref.lower() for ref in response.lineage.source_refs)


def test_alias_expansion_includes_relation_provenance_and_observation(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    response = KeywordGraph(snapshot_store).analyze_query_recall(
        QueryRecallRequest(
            request_id="req-react-alias",
            provider="cts",
            query_text="React",
            max_alternatives=10,
        )
    )

    react_js = next(
        alternative
        for alternative in response.alternatives
        if alternative.target_surface_id == "surface:react-js"
    )
    assert react_js.query_text == "React.js"
    assert react_js.relation_type == "alias"
    assert react_js.confidence == 0.95
    assert react_js.source_concept_id == "concept:react"
    assert react_js.source_surface_id == "surface:react"
    assert react_js.target_surface_id == "surface:react-js"
    assert react_js.evidence_type == "fixture"
    assert react_js.evidence_ref == "relation:react-alias"
    assert react_js.observation is not None
    assert react_js.observation.provider == "cts"
    assert react_js.observation.surface_id == "surface:react-js"
    assert react_js.observation.recall_bucket == "healthy"


def test_request_provider_selects_matching_observation_rows(
    snapshot_store: SQLiteSnapshotStore,
) -> None:
    graph = KeywordGraph(snapshot_store)

    cts_response = graph.analyze_query_recall(
        QueryRecallRequest(
            request_id="req-cts-python", provider="cts", query_text="Python"
        )
    )
    liepin_response = graph.analyze_query_recall(
        QueryRecallRequest(
            request_id="req-liepin-python", provider="liepin", query_text="Python"
        )
    )

    assert cts_response.input_observations[0].provider == "cts"
    assert cts_response.input_observations[0].total == 42
    assert cts_response.input_observations[0].recall_bucket == "healthy"
    assert liepin_response.input_observations[0].provider == "liepin"
    assert liepin_response.input_observations[0].total == 7
    assert liepin_response.input_observations[0].recall_bucket == "too_narrow"
