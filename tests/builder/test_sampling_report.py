from __future__ import annotations

import csv
import json
from pathlib import Path

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.sampling_report import write_sampling_reports


def test_sampling_report_csv_includes_review_fields_and_risk_reasons(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    csv_path = tmp_path / "sampling.csv"
    jsonl_path = tmp_path / "sampling.jsonl"
    try:
        _insert_sampling_fixture(store)

        report = write_sampling_reports(
            store,
            csv_path=csv_path,
            jsonl_path=jsonl_path,
            builder_run_id="run-sampling",
        )

        rows = list(csv.DictReader(csv_path.open(newline="")))
        assert report.row_count == 5
        assert rows[0].keys() >= {
            "risk_reason",
            "evidence_count",
            "proposed_action",
            "target_ids",
        }
        by_reason = {row["risk_reason"]: row for row in rows}
        assert by_reason["ambiguous_text"]["target_ids"] == "surface:go"
        assert by_reason["ambiguous_text"]["evidence_count"] == "3"
        assert by_reason["ambiguous_text"]["proposed_action"] == "review_surface"
        assert by_reason["high_frequency_new_surface"]["target_ids"] == "surface:python"
        assert by_reason["weak_alias"]["target_ids"] == (
            "relation:weak-alias;surface:py;surface:python"
        )
        assert by_reason["company_like_blocker"]["target_ids"] == "blocked:acme"
        assert by_reason["concept_merge_risk"]["target_ids"] == (
            "concept:kubernetes;surface:k8s;surface:kubernetes"
        )
    finally:
        store.close()


def test_sampling_report_jsonl_is_machine_readable_and_replayable(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    csv_path = tmp_path / "sampling.csv"
    jsonl_path = tmp_path / "sampling.jsonl"
    try:
        _insert_sampling_fixture(store)

        write_sampling_reports(
            store,
            csv_path=csv_path,
            jsonl_path=jsonl_path,
            builder_run_id="run-sampling",
        )

        replayed = [
            json.loads(line)
            for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        ]
        assert [row["risk_reason"] for row in replayed] == [
            "ambiguous_text",
            "high_frequency_new_surface",
            "weak_alias",
            "company_like_blocker",
            "concept_merge_risk",
        ]
        assert all(isinstance(row["target_ids"], list) for row in replayed)
        assert all(isinstance(row["evidence"], list) for row in replayed)
        assert replayed[-1]["target_type"] == "concept_merge"
        assert replayed[-1]["target_ids"] == [
            "concept:kubernetes",
            "surface:k8s",
            "surface:kubernetes",
        ]
    finally:
        store.close()


def _insert_sampling_fixture(store: BuildStore) -> None:
    now = "2026-05-31T00:00:00Z"
    for raw, norm, jd_df, tf_total, ambiguity, specificity in (
        ("Go", "go", 3, 3, 0.9, 0.2),
        ("Python", "python", 8, 12, 0.1, 0.9),
        ("Py", "py", 1, 1, 0.45, 0.5),
        ("Kubernetes", "kubernetes", 4, 4, 0.1, 0.9),
        ("K8s", "k8s", 2, 2, 0.25, 0.85),
    ):
        store.insert_surface(
            surface_id=f"surface:{norm}",
            text_raw=raw,
            text_norm=norm,
            display_text=raw,
            language="en",
            token_class="tool",
            query_safe=True,
            is_exact_phrase_preferred=False,
            ambiguity_score=ambiguity,
            specificity_score=specificity,
            jd_df=jd_df,
            jd_tf_total=tf_total,
            serving_status="active",
            created_at=now,
            updated_at=now,
        )
    store.insert_surface_relation(
        relation_id="relation:weak-alias",
        from_surface_id="surface:py",
        to_surface_id="surface:python",
        relation_type="alias",
        confidence=0.52,
        evidence_type="abbreviation",
        created_by="fixture",
        status="active",
    )
    store.insert_concept(
        concept_id="concept:kubernetes",
        canonical_label="Kubernetes",
        concept_type="tool",
        description="Potentially risky merge",
        primary_surface_id="surface:kubernetes",
        surface_count=2,
        jd_df=4,
        stability_score=0.62,
        review_status="pending",
        created_at=now,
        updated_at=now,
    )
    store.insert_concept_surface(
        concept_id="concept:kubernetes",
        surface_id="surface:kubernetes",
        confidence=1.0,
        source="fixture",
        status="active",
    )
    store.insert_concept_surface(
        concept_id="concept:kubernetes",
        surface_id="surface:k8s",
        confidence=0.63,
        source="derived_relation",
        status="active",
    )
    store.insert_jd_document(
        jd_id="jd-1",
        source="fixture",
        source_ref="fixture://jd-1",
        title_raw="Fixture",
        jd_text_ref="inline",
        jd_text="Fixture",
        content_hash="hash:jd-1",
        language="en",
        captured_at=now,
        created_at=now,
        quality_flags_json="[]",
    )
    store.insert_jd_section(
        section_id="section:jd-1:company",
        jd_id="jd-1",
        section_type="company",
        text="Acme AI",
        start_offset=0,
        end_offset=7,
        confidence=0.95,
    )
    store.insert_blocked_surface_candidate(
        candidate_id="blocked:acme",
        jd_id="jd-1",
        section_id="section:jd-1:company",
        surface_text_raw="Acme AI",
        surface_text_norm="acme ai",
        reason_code="company_like",
        evidence_text="Acme AI",
        extractor_name="fixture",
    )
