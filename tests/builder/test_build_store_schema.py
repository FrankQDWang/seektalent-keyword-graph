from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.builder.build_store import BuildStore


def test_build_store_initializes_schema_and_round_trips_all_owned_entities(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        store.insert_builder_run(
            builder_run_id="run-1",
            started_at="2026-05-31T00:00:00Z",
            input_corpus_version="corpus-1",
            status="running",
            report_json="{}",
        )
        store.insert_jd_document(
            jd_id="jd-1",
            source="fixture",
            source_ref="fixture://jd-1",
            title_raw="ML Engineer",
            jd_text_ref="inline",
            jd_text="Python and ML",
            content_hash="hash-1",
            language="en",
            captured_at="2026-05-31T00:00:00Z",
            created_at="2026-05-31T00:00:00Z",
            quality_flags_json="[]",
        )
        store.insert_jd_section(
            section_id="section-1",
            jd_id="jd-1",
            section_type="requirements",
            text="Python and ML",
            start_offset=0,
            end_offset=13,
            confidence=0.95,
        )
        store.insert_keyword_mention(
            mention_id="mention-1",
            jd_id="jd-1",
            section_id="section-1",
            surface_text_raw="Python",
            surface_text_norm="python",
            mention_type="skill",
            requirement_strength="required",
            evidence_text="Python",
            start_offset=0,
            end_offset=6,
            extractor_name="rules",
            extractor_version="v1",
            confidence=0.9,
            review_status="pending",
        )
        store.insert_blocked_surface_candidate(
            candidate_id="blocked-1",
            jd_id="jd-1",
            section_id="section-1",
            surface_text_raw="Acme",
            surface_text_norm="acme",
            reason_code="company_like",
            evidence_text="Acme",
            extractor_name="rules",
        )
        store.insert_surface(
            surface_id="surface-1",
            text_raw="Python",
            text_norm="python",
            display_text="Python",
            language="en",
            token_class="skill",
            query_safe=True,
            is_exact_phrase_preferred=False,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=1,
            jd_tf_total=2,
            serving_status="active",
            created_at="2026-05-31T00:00:00Z",
            updated_at="2026-05-31T00:00:00Z",
        )
        store.insert_concept(
            concept_id="concept-1",
            canonical_label="Python",
            concept_type="language",
            description="Python language",
            primary_surface_id="surface-1",
            surface_count=1,
            jd_df=1,
            stability_score=0.8,
            review_status="approved",
            created_at="2026-05-31T00:00:00Z",
            updated_at="2026-05-31T00:00:00Z",
        )
        store.insert_concept_surface(
            concept_id="concept-1",
            surface_id="surface-1",
            confidence=0.95,
            source="rules",
            status="active",
        )
        store.insert_surface_relation(
            relation_id="relation-1",
            from_surface_id="surface-1",
            to_surface_id="surface-1",
            relation_type="alias",
            confidence=0.7,
            evidence_type="cooccurrence",
            created_by="builder",
            status="active",
        )
        store.insert_cooccurrence_edge(
            edge_id="edge-1",
            surface_id_a="surface-1",
            surface_id_b="surface-1",
            window_type="jd",
            cooccur_count=1,
            pmi=0.2,
            jaccard=1.0,
            support=1.0,
            last_computed_at="2026-05-31T00:00:00Z",
        )
        store.insert_probe_job(
            probe_job_id="probe-1",
            provider="cts",
            surface_id="surface-1",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            priority=1,
            dedupe_key="python|keyword",
            scheduled_at="2026-05-31T00:00:00Z",
            not_before="2026-05-31T00:00:00Z",
            attempt_count=0,
            status="scheduled",
            rate_limit_bucket="fake",
            created_reason="new_surface",
            last_error_code=None,
        )
        probe_job = store.list_probe_jobs("surface-1")[0]
        assert probe_job["provider"] == "cts"
        assert probe_job["query_hash"] == "hash-python"

        store.insert_provider_recall_observation(
            observation_id="obs-1",
            provider="cts",
            probe_job_id="probe-1",
            surface_id="surface-1",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            total=42,
            latency_ms=12,
            status="ok",
            error_code=None,
            observed_at="2026-05-31T00:00:00Z",
            recall_bucket="healthy",
            provider_api_version="fake-v1",
            builder_run_id="run-1",
            evidence_ref="probe:obs-1",
        )
        store.insert_cts_recall_observation(
            observation_id="obs-compat",
            probe_job_id="probe-1",
            surface_id="surface-1",
            query_text="Python",
            query_hash="hash-python",
            query_mode="keyword",
            total=42,
            latency_ms=12,
            status="ok",
            error_code=None,
            observed_at="2026-05-31T00:00:00Z",
            cts_api_version="fake-v1",
            builder_run_id="run-1",
        )
        store.insert_review_decision(
            decision_id="decision-1",
            target_type="surface",
            target_id="surface-1",
            decision="approve",
            reason="fixture",
            reviewer="tester",
            reviewed_at="2026-05-31T00:00:00Z",
        )
        store.insert_build_event(
            event_id="event-1",
            builder_run_id="run-1",
            event_type="import",
            message="imported",
            payload_json="{}",
            created_at="2026-05-31T00:00:00Z",
        )

        assert store.get_jd_document("jd-1")["title_raw"] == "ML Engineer"
        assert store.list_sections("jd-1")[0]["section_type"] == "requirements"
        assert store.list_mentions("jd-1")[0]["surface_text_norm"] == "python"
        assert store.list_blocked_candidates("jd-1")[0]["reason_code"] == "company_like"
        assert store.get_surface("surface-1")["display_text"] == "Python"
        assert store.get_concept("concept-1")["canonical_label"] == "Python"
        assert store.list_concept_surfaces("concept-1")[0]["surface_id"] == "surface-1"
        assert store.list_surface_relations("surface-1")[0]["relation_type"] == "alias"
        assert store.list_cooccurrence_edges("surface-1")[0]["edge_id"] == "edge-1"
        assert store.list_probe_jobs("surface-1")[0]["probe_job_id"] == "probe-1"
        observations = store.list_observations("surface-1")
        assert {observation["provider"] for observation in observations} == {"cts"}
        assert observations[0]["total"] == 42
        assert observations[0]["recall_bucket"] == "healthy"
        assert observations[0]["provider_api_version"] == "fake-v1"
        decision = store.list_review_decisions("surface", "surface-1")[0]
        assert decision["decision"] == "approve"
        assert store.list_build_events("run-1")[0]["message"] == "imported"
    finally:
        store.close()
