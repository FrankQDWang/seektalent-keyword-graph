from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from seektalent_keyword_graph.builder.build_snapshot import (
    BuildSnapshotConfig,
    build_runtime_snapshot,
)
from seektalent_keyword_graph.builder.build_store import BuildStore

NOW = "2026-06-01T00:00:00Z"


def test_build_db_snapshot_to_query_recall_optimization_is_local_only(
    tmp_path: Path,
) -> None:
    build_db = tmp_path / "build.sqlite3"
    _seed_query_recall_build_db(build_db)
    result = build_runtime_snapshot(
        build_db,
        tmp_path / "snapshot",
        BuildSnapshotConfig(
            kg_snapshot_id="kg-qro-integration",
            built_at=NOW,
            source_corpus_version="fixture-qro",
            builder_run_id="run-qro",
            provider_probe_window_start="2026-05-31T00:00:00Z",
            provider_probe_window_end=NOW,
            provider_sources=("cts",),
            default_serving_provider="cts",
        ),
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _RUNTIME_CHECK,
            str(result.snapshot_path),
            str(result.manifest_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        ["React", "React.js", "replace"],
        ["Kubernetes", "Kubernetes", "keep"],
        ["Kubernetes", "Docker", "add_precision_companion"],
        ["Kafka", "Apache Kafka", "replace"],
        ["LLMOps", "LLMOps", "score_only"],
        ["GraphQL", "GraphQL", "fallback"],
    ]


_RUNTIME_CHECK = r"""
import json
import os
import socket
import sys

os.environ["KEYWORD_GRAPH_CTS_TENANT_SECRET"] = "do-not-read"
original_getenv = os.getenv


def guarded_getenv(key, default=None):
    if key.startswith("KEYWORD_GRAPH_CTS_"):
        raise AssertionError(f"runtime read forbidden CTS env var {key}")
    return original_getenv(key, default)


OriginalSocket = socket.socket


class GuardedSocket(OriginalSocket):
    def __new__(cls, *args, **kwargs):
        raise AssertionError("runtime query recall attempted network I/O")


def forbidden_runtime_modules():
    return {
        name
        for name in sys.modules
        if name == "seektalent"
        or name.startswith(
            (
                "seektalent_keyword_graph.builder",
                "seektalent_keyword_graph.cts",
            )
        )
    }


os.getenv = guarded_getenv
socket.socket = GuardedSocket
forbidden_before = forbidden_runtime_modules()

from seektalent_keyword_graph.contracts import QueryRecallRequest
from seektalent_keyword_graph.engine import KeywordGraph

if forbidden_runtime_modules() != forbidden_before:
    raise AssertionError("runtime import loaded builder, CTS, or SeekTalent modules")

graph = KeywordGraph.open(sys.argv[1], sys.argv[2])
try:
    response = graph.optimize_query_terms(
        QueryRecallRequest(
            request_id="req-integration-qro",
            provider="cts",
            query_terms=[
                {"text": "React"},
                {"text": "Kubernetes"},
                {"text": "Kafka"},
                {"text": "LLMOps", "strength": "preferred"},
                {"text": "GraphQL", "strength": "preferred"},
            ],
            max_alternatives=10,
        )
    )
finally:
    graph.close()

if forbidden_runtime_modules() != forbidden_before:
    raise AssertionError("runtime execution loaded builder, CTS, or SeekTalent modules")

print(
    json.dumps(
        [
            [term.source_query_text, term.query_text, term.action]
            for term in response.optimized_terms
        ],
        separators=(",", ":"),
    )
)
"""


def _seed_query_recall_build_db(path: Path) -> None:
    store = BuildStore.open(path)
    try:
        store.insert_builder_run(
            builder_run_id="run-qro",
            started_at="2026-05-31T00:00:00Z",
            finished_at=NOW,
            input_corpus_version="fixture-qro",
            status="succeeded",
            report_json="{}",
        )
        for surface_id, text, bucket in [
            ("surface:react", "React", "zero"),
            ("surface:react-js", "React.js", "healthy"),
            ("surface:kubernetes", "Kubernetes", "too_wide"),
            ("surface:docker", "Docker", "healthy"),
            ("surface:kafka", "Kafka", "stale"),
            ("surface:apache-kafka", "Apache Kafka", "healthy"),
            ("surface:llmops", "LLMOps", "unknown"),
        ]:
            store.insert_surface(
                surface_id=surface_id,
                text_raw=text,
                text_norm=text.casefold(),
                display_text=text,
                language="en",
                token_class="skill",
                query_safe=True,
                is_exact_phrase_preferred=" " in text,
                ambiguity_score=0.1,
                specificity_score=0.9,
                jd_df=1,
                jd_tf_total=1,
                recall_bucket=bucket,
                serving_status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        for concept_id, label, primary_surface_id, members in [
            (
                "concept:react",
                "React",
                "surface:react",
                [("surface:react", 0.95), ("surface:react-js", 0.9)],
            ),
            (
                "concept:kubernetes",
                "Kubernetes",
                "surface:kubernetes",
                [("surface:kubernetes", 0.95)],
            ),
            (
                "concept:docker",
                "Docker",
                "surface:docker",
                [("surface:docker", 0.95)],
            ),
            (
                "concept:kafka",
                "Kafka",
                "surface:kafka",
                [("surface:kafka", 0.95), ("surface:apache-kafka", 0.9)],
            ),
            (
                "concept:llmops",
                "LLMOps",
                "surface:llmops",
                [("surface:llmops", 0.8)],
            ),
        ]:
            store.insert_concept(
                concept_id=concept_id,
                canonical_label=label,
                concept_type="skill",
                description=f"{label} concept",
                primary_surface_id=primary_surface_id,
                surface_count=len(members),
                jd_df=1,
                stability_score=0.9,
                review_status="approved",
                created_at=NOW,
                updated_at=NOW,
            )
            for surface_id, confidence in members:
                store.insert_concept_surface(
                    concept_id=concept_id,
                    surface_id=surface_id,
                    confidence=confidence,
                    source="fixture",
                    status="active",
                )
        for relation_id, from_id, to_id in [
            ("relation:react-alias", "surface:react", "surface:react-js"),
            ("relation:kafka-alias", "surface:kafka", "surface:apache-kafka"),
        ]:
            store.insert_surface_relation(
                relation_id=relation_id,
                from_surface_id=from_id,
                to_surface_id=to_id,
                relation_type="alias",
                confidence=0.95,
                evidence_type="fixture",
                created_by="fixture",
                status="active",
            )
        store.insert_cooccurrence_edge(
            edge_id="edge:kubernetes-docker",
            surface_id_a="surface:kubernetes",
            surface_id_b="surface:docker",
            window_type="jd",
            cooccur_count=8,
            pmi=3.1,
            jaccard=0.4,
            support=0.88,
            last_computed_at=NOW,
        )
        for surface_id, query_text, total, bucket, observed_at in [
            ("surface:react", "react", 0, "zero", NOW),
            ("surface:react-js", "react-js", 50, "healthy", NOW),
            ("surface:kubernetes", "kubernetes", 1500, "too_wide", NOW),
            ("surface:docker", "docker", 60, "healthy", NOW),
            ("surface:kafka", "kafka", 80, "stale", "2025-01-01T00:00:00Z"),
            ("surface:apache-kafka", "apache-kafka", 55, "healthy", NOW),
            ("surface:llmops", "llmops", None, "unknown", NOW),
        ]:
            probe_job_id = f"probe:{surface_id}"
            store.insert_probe_job(
                probe_job_id=probe_job_id,
                provider="cts",
                surface_id=surface_id,
                query_text=query_text,
                query_hash=f"hash:{surface_id}",
                query_mode="keyword",
                priority=1,
                dedupe_key=f"cts:{surface_id}",
                scheduled_at=NOW,
                not_before=NOW,
                attempt_count=0,
                status="succeeded",
                rate_limit_bucket="fake",
                created_reason="fixture",
                last_error_code=None,
            )
            store.insert_provider_recall_observation(
                observation_id=f"obs:cts:{surface_id}",
                provider="cts",
                probe_job_id=probe_job_id,
                surface_id=surface_id,
                query_text=query_text,
                query_hash=f"hash:{surface_id}",
                query_mode="keyword",
                total=total,
                latency_ms=10,
                status="unknown" if total is None else "ok",
                error_code=None,
                observed_at=observed_at,
                recall_bucket=bucket,
                provider_api_version="fixture",
                builder_run_id="run-qro",
                evidence_ref=f"fixture:obs:cts:{surface_id}",
            )
    finally:
        store.close()
