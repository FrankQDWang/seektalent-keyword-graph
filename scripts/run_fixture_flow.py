from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.builder.build_relations import build_relations
from seektalent_keyword_graph.builder.build_snapshot import (
    BuildSnapshotConfig,
    build_runtime_snapshot,
)
from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.cooccurrence import build_cooccurrence_edges
from seektalent_keyword_graph.builder.extract_surfaces import extract_surfaces
from seektalent_keyword_graph.builder.import_jds import import_jsonl_jds
from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryRecallRequest
from seektalent_keyword_graph.domain.classification import classify_surface
from seektalent_keyword_graph.domain.normalization import normalize_surface
from seektalent_keyword_graph.domain.provider_recall import (
    recall_bucket_for_observation,
)
from seektalent_keyword_graph.engine import KeywordGraph
from seektalent_keyword_graph.observability.replay_report import build_replay_report

NOW = "2026-06-01T00:00:00Z"
WINDOW_START = "2026-05-31T00:00:00Z"
STALE_AT = "2025-01-01T00:00:00Z"
BUILDER_RUN_ID = "run-eval-fixture"
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "eval_jds"
    / "full_replay_flow.jsonl"
)
PROVIDERS = ("boss", "cts", "liepin")


@dataclass(frozen=True)
class FixtureFlowResult:
    work_dir: Path
    fixture_path: Path
    build_db_path: Path
    snapshot_path: Path
    manifest_path: Path
    replay_report_path: Path
    import_report: Any
    extraction_report: Any
    relation_report: Any
    cooccurrence_report: Any
    query_plan_responses: list[Any]
    query_recall_responses: list[Any]
    replay_report: dict[str, object]


def run_fixture_flow(
    work_dir: str | Path,
    *,
    jd_jsonl_path: str | Path | None = None,
) -> FixtureFlowResult:
    """Run the local eval JD-to-runtime flow without live provider calls."""

    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    fixture_path = Path(jd_jsonl_path) if jd_jsonl_path is not None else FIXTURE_PATH
    build_db_path = root / "build.sqlite3"
    if build_db_path.exists():
        build_db_path.unlink()

    store = BuildStore.open(build_db_path)
    try:
        import_report = import_jsonl_jds(
            store, fixture_path, builder_run_id=BUILDER_RUN_ID
        )
        extraction_report = extract_surfaces(store, builder_run_id=BUILDER_RUN_ID)
        relation_report = build_relations(store, builder_run_id=BUILDER_RUN_ID)
        cooccurrence_report = build_cooccurrence_edges(
            store, builder_run_id=BUILDER_RUN_ID
        )
        _apply_eval_enrichments(store)
        _seed_provider_observations(store)
        _finish_builder_run(store)
    finally:
        store.close()

    snapshot_dir = root / "snapshot"
    snapshot_result = build_runtime_snapshot(
        build_db_path,
        snapshot_dir,
        BuildSnapshotConfig(
            kg_snapshot_id="kg-eval-fixture",
            built_at=NOW,
            source_corpus_version="eval-fixture-v1",
            builder_run_id=BUILDER_RUN_ID,
            provider_probe_window_start=WINDOW_START,
            provider_probe_window_end=NOW,
            provider_sources=PROVIDERS,
            default_serving_provider="cts",
        ),
    )

    graph = KeywordGraph.open(
        snapshot_result.snapshot_path, snapshot_result.manifest_path
    )
    try:
        plan_responses = _run_plan_cases(graph)
        recall_responses = _run_recall_cases(graph)
    finally:
        graph.close()

    replay_report = build_replay_report(
        plan_responses=plan_responses,
        recall_responses=recall_responses,
        provider_recall_summary=_provider_recall_summary(snapshot_result.snapshot_path),
    )
    replay_report_path = root / "replay-report.json"
    replay_report_path.write_text(
        json.dumps(replay_report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    return FixtureFlowResult(
        work_dir=root,
        fixture_path=fixture_path,
        build_db_path=build_db_path,
        snapshot_path=snapshot_result.snapshot_path,
        manifest_path=snapshot_result.manifest_path,
        replay_report_path=replay_report_path,
        import_report=import_report,
        extraction_report=extraction_report,
        relation_report=relation_report,
        cooccurrence_report=cooccurrence_report,
        query_plan_responses=plan_responses,
        query_recall_responses=recall_responses,
        replay_report=replay_report,
    )


def _apply_eval_enrichments(store: BuildStore) -> None:
    for text, token_class in (
        ("React.js", "framework"),
        ("Apache Kafka", "tool"),
        ("Vector Search", "method"),
        ("GraphQL", "technical"),
    ):
        _ensure_surface_with_concept(store, text=text, token_class=token_class)

    _ensure_relation(store, "React", "React.js", "alias")
    _ensure_relation(store, "Kafka", "Apache Kafka", "alias")
    _ensure_relation(store, "AIOps", "LLMOps", "alias")

    _ensure_cooccurrence(store, "Kubernetes", "Docker")


def _ensure_surface_with_concept(
    store: BuildStore, *, text: str, token_class: str
) -> None:
    normalized = normalize_surface(text)
    surface_id = _surface_id(text)
    existing = store.get_surface(surface_id)
    if existing is None:
        classification = classify_surface(text)
        store.insert_surface(
            surface_id=surface_id,
            text_raw=text,
            text_norm=normalized.text_norm,
            display_text=text,
            language=classification.language,
            token_class=token_class,
            query_safe=True,
            is_exact_phrase_preferred=" " in normalized.text_norm
            or "." in normalized.text_norm,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=1,
            jd_tf_total=1,
            recall_bucket="unknown",
            serving_status="active",
            created_at=NOW,
            updated_at=NOW,
        )

    concept_id = f"concept:{normalized.text_norm}"
    if store.get_concept(concept_id) is None:
        store.insert_concept(
            concept_id=concept_id,
            canonical_label=text,
            concept_type=token_class,
            description=f"Eval fixture concept for {text}",
            primary_surface_id=surface_id,
            surface_count=1,
            jd_df=1,
            stability_score=0.95,
            review_status="approved",
            created_at=NOW,
            updated_at=NOW,
        )
        store.insert_concept_surface(
            concept_id=concept_id,
            surface_id=surface_id,
            confidence=0.95,
            source="eval_fixture_enrichment",
            status="active",
        )


def _ensure_relation(
    store: BuildStore, left_text: str, right_text: str, relation_type: str
) -> None:
    left_id = _surface_id(left_text)
    right_id = _surface_id(right_text)
    relation_id = (
        f"relation:eval:{relation_type}:{_slug(left_text)}:{_slug(right_text)}"
    )
    row = store.connection.execute(
        "select relation_id from surface_relations where relation_id = ?",
        (relation_id,),
    ).fetchone()
    if row is not None:
        return
    store.insert_surface_relation(
        relation_id=relation_id,
        from_surface_id=left_id,
        to_surface_id=right_id,
        relation_type=relation_type,
        confidence=0.95,
        evidence_type="eval_fixture_enrichment",
        created_by="run_fixture_flow",
        status="active",
    )


def _ensure_cooccurrence(store: BuildStore, left_text: str, right_text: str) -> None:
    left_id = _surface_id(left_text)
    right_id = _surface_id(right_text)
    ordered = tuple(sorted((left_id, right_id)))
    edge_id = f"edge:eval:{_slug(ordered[0])}:{_slug(ordered[1])}"
    row = store.connection.execute(
        "select edge_id from cooccurrence_edges where edge_id = ?",
        (edge_id,),
    ).fetchone()
    if row is not None:
        return
    store.insert_cooccurrence_edge(
        edge_id=edge_id,
        surface_id_a=ordered[0],
        surface_id_b=ordered[1],
        window_type="eval_fixture",
        cooccur_count=8,
        pmi=3.1,
        jaccard=0.4,
        support=0.88,
        last_computed_at=NOW,
    )


def _seed_provider_observations(store: BuildStore) -> None:
    rows = store.connection.execute(
        """
        select surface_id, display_text
        from surfaces
        where serving_status = 'active' and query_safe = 1
        order by surface_id
        """
    ).fetchall()
    for provider in PROVIDERS:
        for row in rows:
            surface_id = str(row["surface_id"])
            display_text = str(row["display_text"])
            total, status, observed_at = _provider_observation(provider, surface_id)
            bucket = recall_bucket_for_observation(
                total=total,
                status=status,
                observed_at=observed_at,
                reference_time=NOW,
            )
            probe_job_id = f"probe:{provider}:{surface_id}"
            query_hash = f"hash:{provider}:{surface_id}"
            store.insert_probe_job(
                probe_job_id=probe_job_id,
                provider=provider,
                surface_id=surface_id,
                query_text=display_text,
                query_hash=query_hash,
                query_mode="keyword",
                priority=1,
                dedupe_key=f"{provider}:{surface_id}:keyword",
                scheduled_at=NOW,
                not_before=NOW,
                attempt_count=0,
                status="succeeded",
                rate_limit_bucket=f"eval-{provider}",
                created_reason="eval_fixture",
                last_error_code=None,
            )
            store.insert_provider_recall_observation(
                observation_id=f"obs:{provider}:{surface_id}",
                provider=provider,
                probe_job_id=probe_job_id,
                surface_id=surface_id,
                query_text=display_text,
                query_hash=query_hash,
                query_mode="keyword",
                total=total,
                latency_ms=10,
                status=status,
                error_code=None,
                observed_at=observed_at,
                recall_bucket=bucket,
                provider_api_version="eval-fixture",
                builder_run_id=BUILDER_RUN_ID,
                evidence_ref=f"eval:{provider}:{surface_id}",
            )


def _provider_observation(
    provider: str, surface_id: str
) -> tuple[int | None, str, str]:
    if provider == "cts":
        overrides: dict[str, tuple[int | None, str, str]] = {
            "surface:kubernetes": (1500, "ok", NOW),
            "surface:react": (0, "ok", NOW),
            "surface:kafka": (80, "ok", STALE_AT),
            "surface:llmops": (None, "unknown", NOW),
        }
        return overrides.get(surface_id, (42, "ok", NOW))
    if provider == "liepin":
        overrides = {
            "surface:python 3": (7, "ok", NOW),
            "surface:aiops": (0, "ok", NOW),
        }
        return overrides.get(surface_id, (33, "ok", NOW))
    if provider == "boss":
        overrides = {
            "surface:kubernetes": (1500, "ok", NOW),
            "surface:react": (0, "ok", NOW),
        }
        return overrides.get(surface_id, (75, "ok", NOW))
    raise ValueError(f"unsupported eval provider: {provider}")


def _finish_builder_run(store: BuildStore) -> None:
    store.connection.execute(
        """
        update builder_runs
        set finished_at = ?, status = ?, report_json = ?
        where builder_run_id = ?
        """,
        (NOW, "succeeded", "{}", BUILDER_RUN_ID),
    )
    store.connection.commit()


def _run_plan_cases(graph: KeywordGraph) -> list[Any]:
    requests = [
        QueryPlanRequest(
            request_id="plan-full-bundle-matrix",
            requirement_terms=[
                {"text": "Python 3", "strength": "required"},
                {"text": "Kubernetes", "strength": "required"},
                {"text": "React", "strength": "required"},
                {"text": "Kafka", "strength": "preferred"},
                {"text": "LLMOps", "strength": "preferred"},
                {"text": "Acme Corp", "strength": "preferred"},
                {"text": "Platform Team", "strength": "preferred"},
            ],
            max_query_bundles=10,
            include_exploration=True,
        ),
        QueryPlanRequest(
            request_id="plan-fallback-only",
            requirement_terms=[{"text": "CobolScript", "strength": "required"}],
            max_query_bundles=5,
        ),
    ]
    return [graph.build_query_plan(request) for request in requests]


def _run_recall_cases(graph: KeywordGraph) -> list[Any]:
    requests = [
        QueryRecallRequest(
            request_id="recall-cts-term-pool",
            provider="cts",
            query_terms=[
                {"text": "React"},
                {"text": "Kubernetes"},
                {"text": "Kafka"},
                {"text": "LLMOps", "strength": "preferred"},
                {"text": "GhostLang", "strength": "preferred"},
            ],
            max_alternatives=10,
        ),
        QueryRecallRequest(
            request_id="recall-liepin-provider",
            provider="liepin",
            query_terms=[
                {"text": "Python 3"},
                {"text": "React"},
                {"text": "LLMOps", "strength": "preferred"},
            ],
            max_alternatives=10,
        ),
        QueryRecallRequest(
            request_id="recall-boss-provider",
            provider="boss",
            query_terms=[
                {"text": "Python 3"},
                {"text": "Kubernetes"},
                {"text": "React"},
            ],
            max_alternatives=10,
        ),
        QueryRecallRequest(
            request_id="recall-phrase-without-observation",
            provider="cts",
            query_terms=[{"text": "Vector Search"}],
            query_mode="phrase",
            max_alternatives=10,
        ),
    ]
    return [graph.optimize_query_terms(request) for request in requests]


def _provider_recall_summary(snapshot_path: Path) -> dict[str, dict[str, int]]:
    with sqlite3.connect(snapshot_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select provider, recall_bucket, count(*) as count
            from provider_recall_observations
            group by provider, recall_bucket
            order by provider, recall_bucket
            """
        ).fetchall()
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        summary.setdefault(str(row["provider"]), {})[
            str(row["recall_bucket"])
        ] = int(row["count"])
    return summary


def _surface_id(text: str) -> str:
    return f"surface:{normalize_surface(text).text_norm}"


def _slug(text: str) -> str:
    return (
        text.removeprefix("surface:")
        .replace(" ", "-")
        .replace(".", "")
        .replace("/", "-")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--jd-jsonl", default=None)
    args = parser.parse_args(argv)

    result = run_fixture_flow(args.work_dir, jd_jsonl_path=args.jd_jsonl)
    payload = {
        "build_db_path": str(result.build_db_path),
        "snapshot_path": str(result.snapshot_path),
        "manifest_path": str(result.manifest_path),
        "replay_report_path": str(result.replay_report_path),
        "summary": result.replay_report["summary"],
    }
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
