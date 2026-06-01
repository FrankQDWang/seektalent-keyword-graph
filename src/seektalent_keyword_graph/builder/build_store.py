"""SQLite build database adapter."""

# ruff: noqa: E501

from __future__ import annotations

import sqlite3
from pathlib import Path

from seektalent_keyword_graph.storage.sqlite_migrations import migrate_build_db


class BuildStore:
    """Explicit SQL adapter for builder state."""

    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self.connection = connection
        self.path = path
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: str | Path) -> BuildStore:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("pragma foreign_keys = on")
        migrate_build_db(conn)
        return cls(conn, db_path)

    def close(self) -> None:
        self.connection.close()

    def insert_builder_run(
        self,
        *,
        builder_run_id: str,
        started_at: str,
        input_corpus_version: str,
        status: str,
        report_json: str,
        finished_at: str | None = None,
    ) -> None:
        self._execute(
            """
            insert into builder_runs(
              builder_run_id, started_at, finished_at, input_corpus_version, status, report_json
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (
                builder_run_id,
                started_at,
                finished_at,
                input_corpus_version,
                status,
                report_json,
            ),
        )

    def insert_jd_document(
        self,
        *,
        jd_id: str,
        source: str,
        source_ref: str,
        title_raw: str,
        jd_text_ref: str,
        jd_text: str,
        content_hash: str,
        language: str,
        captured_at: str,
        created_at: str,
        quality_flags_json: str,
    ) -> None:
        self._execute(
            """
            insert into jd_documents(
              jd_id, source, source_ref, title_raw, jd_text_ref, jd_text, content_hash,
              language, captured_at, created_at, quality_flags_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jd_id,
                source,
                source_ref,
                title_raw,
                jd_text_ref,
                jd_text,
                content_hash,
                language,
                captured_at,
                created_at,
                quality_flags_json,
            ),
        )

    def insert_jd_section(
        self,
        *,
        section_id: str,
        jd_id: str,
        section_type: str,
        text: str,
        start_offset: int,
        end_offset: int,
        confidence: float,
    ) -> None:
        self._execute(
            """
            insert into jd_sections(
              section_id, jd_id, section_type, text, start_offset, end_offset, confidence
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (section_id, jd_id, section_type, text, start_offset, end_offset, confidence),
        )

    def insert_keyword_mention(
        self,
        *,
        mention_id: str,
        jd_id: str,
        section_id: str,
        surface_text_raw: str,
        surface_text_norm: str,
        mention_type: str,
        requirement_strength: str,
        evidence_text: str,
        start_offset: int,
        end_offset: int,
        extractor_name: str,
        extractor_version: str,
        confidence: float,
        review_status: str,
    ) -> None:
        self._execute(
            """
            insert into keyword_mentions(
              mention_id, jd_id, section_id, surface_text_raw, surface_text_norm,
              mention_type, requirement_strength, evidence_text, start_offset, end_offset,
              extractor_name, extractor_version, confidence, review_status
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mention_id,
                jd_id,
                section_id,
                surface_text_raw,
                surface_text_norm,
                mention_type,
                requirement_strength,
                evidence_text,
                start_offset,
                end_offset,
                extractor_name,
                extractor_version,
                confidence,
                review_status,
            ),
        )

    def insert_blocked_surface_candidate(
        self,
        *,
        candidate_id: str,
        jd_id: str,
        section_id: str,
        surface_text_raw: str,
        surface_text_norm: str,
        reason_code: str,
        evidence_text: str,
        extractor_name: str,
    ) -> None:
        self._execute(
            """
            insert into blocked_surface_candidates(
              candidate_id, jd_id, section_id, surface_text_raw, surface_text_norm,
              reason_code, evidence_text, extractor_name
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                jd_id,
                section_id,
                surface_text_raw,
                surface_text_norm,
                reason_code,
                evidence_text,
                extractor_name,
            ),
        )

    def insert_surface(
        self,
        *,
        surface_id: str,
        text_raw: str,
        text_norm: str,
        display_text: str,
        language: str,
        token_class: str,
        query_safe: bool,
        is_exact_phrase_preferred: bool,
        ambiguity_score: float,
        specificity_score: float,
        jd_df: int,
        jd_tf_total: int,
        serving_status: str,
        created_at: str,
        updated_at: str,
        recall_bucket: str = "unknown",
    ) -> None:
        self._execute(
            """
            insert into surfaces(
              surface_id, text_raw, text_norm, display_text, language, token_class,
              query_safe, is_exact_phrase_preferred, ambiguity_score, specificity_score,
              jd_df, jd_tf_total, recall_bucket, serving_status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                surface_id,
                text_raw,
                text_norm,
                display_text,
                language,
                token_class,
                int(query_safe),
                int(is_exact_phrase_preferred),
                ambiguity_score,
                specificity_score,
                jd_df,
                jd_tf_total,
                recall_bucket,
                serving_status,
                created_at,
                updated_at,
            ),
        )

    def insert_concept(
        self,
        *,
        concept_id: str,
        canonical_label: str,
        concept_type: str,
        description: str,
        primary_surface_id: str | None,
        surface_count: int,
        jd_df: int,
        stability_score: float,
        review_status: str,
        created_at: str,
        updated_at: str,
    ) -> None:
        self._execute(
            """
            insert into concepts(
              concept_id, canonical_label, concept_type, description, primary_surface_id,
              surface_count, jd_df, stability_score, review_status, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                concept_id,
                canonical_label,
                concept_type,
                description,
                primary_surface_id,
                surface_count,
                jd_df,
                stability_score,
                review_status,
                created_at,
                updated_at,
            ),
        )

    def insert_concept_surface(
        self,
        *,
        concept_id: str,
        surface_id: str,
        confidence: float,
        source: str,
        status: str,
    ) -> None:
        self._execute(
            """
            insert into concept_surfaces(concept_id, surface_id, confidence, source, status)
            values (?, ?, ?, ?, ?)
            """,
            (concept_id, surface_id, confidence, source, status),
        )

    def insert_surface_relation(
        self,
        *,
        relation_id: str,
        from_surface_id: str,
        to_surface_id: str,
        relation_type: str,
        confidence: float,
        evidence_type: str,
        created_by: str,
        status: str,
    ) -> None:
        self._execute(
            """
            insert into surface_relations(
              relation_id, from_surface_id, to_surface_id, relation_type, confidence,
              evidence_type, created_by, status
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_id,
                from_surface_id,
                to_surface_id,
                relation_type,
                confidence,
                evidence_type,
                created_by,
                status,
            ),
        )

    def insert_cooccurrence_edge(
        self,
        *,
        edge_id: str,
        surface_id_a: str,
        surface_id_b: str,
        window_type: str,
        cooccur_count: int,
        pmi: float,
        jaccard: float,
        support: float,
        last_computed_at: str,
    ) -> None:
        self._execute(
            """
            insert into cooccurrence_edges(
              edge_id, surface_id_a, surface_id_b, window_type, cooccur_count,
              pmi, jaccard, support, last_computed_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge_id,
                surface_id_a,
                surface_id_b,
                window_type,
                cooccur_count,
                pmi,
                jaccard,
                support,
                last_computed_at,
            ),
        )

    def insert_probe_job(
        self,
        *,
        probe_job_id: str,
        surface_id: str,
        query_text: str,
        query_mode: str,
        priority: int,
        dedupe_key: str,
        scheduled_at: str,
        not_before: str,
        attempt_count: int,
        status: str,
        rate_limit_bucket: str,
        created_reason: str,
        last_error_code: str | None,
    ) -> None:
        self._execute(
            """
            insert into probe_jobs(
              probe_job_id, surface_id, query_text, query_mode, priority, dedupe_key,
              scheduled_at, not_before, attempt_count, status, rate_limit_bucket,
              created_reason, last_error_code
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                probe_job_id,
                surface_id,
                query_text,
                query_mode,
                priority,
                dedupe_key,
                scheduled_at,
                not_before,
                attempt_count,
                status,
                rate_limit_bucket,
                created_reason,
                last_error_code,
            ),
        )

    def insert_probe_job_if_absent(
        self,
        *,
        probe_job_id: str,
        surface_id: str,
        query_text: str,
        query_mode: str,
        priority: int,
        dedupe_key: str,
        scheduled_at: str,
        not_before: str,
        attempt_count: int,
        status: str,
        rate_limit_bucket: str,
        created_reason: str,
        last_error_code: str | None,
    ) -> bool:
        try:
            self.insert_probe_job(
                probe_job_id=probe_job_id,
                surface_id=surface_id,
                query_text=query_text,
                query_mode=query_mode,
                priority=priority,
                dedupe_key=dedupe_key,
                scheduled_at=scheduled_at,
                not_before=not_before,
                attempt_count=attempt_count,
                status=status,
                rate_limit_bucket=rate_limit_bucket,
                created_reason=created_reason,
                last_error_code=last_error_code,
            )
        except sqlite3.IntegrityError:
            return False
        return True

    def insert_cts_recall_observation(
        self,
        *,
        observation_id: str,
        probe_job_id: str,
        surface_id: str,
        query_text: str,
        query_hash: str,
        query_mode: str,
        total: int | None,
        latency_ms: int | None,
        status: str,
        error_code: str | None,
        observed_at: str,
        cts_api_version: str,
        builder_run_id: str,
    ) -> None:
        self._execute(
            """
            insert into cts_recall_observations(
              observation_id, probe_job_id, surface_id, query_text, query_hash,
              query_mode, total, latency_ms, status, error_code, observed_at,
              cts_api_version, builder_run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation_id,
                probe_job_id,
                surface_id,
                query_text,
                query_hash,
                query_mode,
                total,
                latency_ms,
                status,
                error_code,
                observed_at,
                cts_api_version,
                builder_run_id,
            ),
        )

    def insert_review_decision(
        self,
        *,
        decision_id: str,
        target_type: str,
        target_id: str,
        decision: str,
        reason: str,
        reviewer: str,
        reviewed_at: str,
    ) -> None:
        self._execute(
            """
            insert into review_decisions(
              decision_id, target_type, target_id, decision, reason, reviewer, reviewed_at
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            (decision_id, target_type, target_id, decision, reason, reviewer, reviewed_at),
        )

    def insert_build_event(
        self,
        *,
        event_id: str,
        builder_run_id: str,
        event_type: str,
        message: str,
        payload_json: str,
        created_at: str,
    ) -> None:
        self._execute(
            """
            insert into build_events(
              event_id, builder_run_id, event_type, message, payload_json, created_at
            ) values (?, ?, ?, ?, ?, ?)
            """,
            (event_id, builder_run_id, event_type, message, payload_json, created_at),
        )

    def get_jd_document(self, jd_id: str) -> dict[str, object] | None:
        return self._fetch_one("select * from jd_documents where jd_id = ?", (jd_id,))

    def list_sections(self, jd_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from jd_sections where jd_id = ? order by start_offset, section_id",
            (jd_id,),
        )

    def list_mentions(self, jd_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from keyword_mentions where jd_id = ? order by start_offset, mention_id",
            (jd_id,),
        )

    def list_blocked_candidates(self, jd_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from blocked_surface_candidates where jd_id = ? order by candidate_id",
            (jd_id,),
        )

    def get_surface(self, surface_id: str) -> dict[str, object] | None:
        return self._fetch_one("select * from surfaces where surface_id = ?", (surface_id,))

    def get_surface_by_norm(self, text_norm: str) -> dict[str, object] | None:
        return self._fetch_one("select * from surfaces where text_norm = ?", (text_norm,))

    def get_concept(self, concept_id: str) -> dict[str, object] | None:
        return self._fetch_one("select * from concepts where concept_id = ?", (concept_id,))

    def list_concept_surfaces(self, concept_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from concept_surfaces where concept_id = ? order by confidence desc, surface_id",
            (concept_id,),
        )

    def list_surface_relations(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from surface_relations where from_surface_id = ? or to_surface_id = ? "
            "order by relation_id",
            (surface_id, surface_id),
        )

    def list_cooccurrence_edges(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from cooccurrence_edges where surface_id_a = ? or surface_id_b = ? "
            "order by edge_id",
            (surface_id, surface_id),
        )

    def list_probe_jobs(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from probe_jobs where surface_id = ? order by priority, probe_job_id",
            (surface_id,),
        )

    def list_active_probe_surfaces(self) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from surfaces where serving_status = ? and query_safe = ? "
            "order by specificity_score desc, surface_id",
            ("active", 1),
        )

    def list_due_probe_jobs(self, due_at: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from probe_jobs where status in (?, ?) and not_before <= ? "
            "order by priority, scheduled_at, probe_job_id",
            ("scheduled", "retry_scheduled", due_at),
        )

    def find_observation_since(
        self,
        *,
        surface_id: str,
        query_hash: str,
        query_mode: str,
        observed_after: str,
    ) -> dict[str, object] | None:
        return self._fetch_one(
            "select * from cts_recall_observations "
            "where surface_id = ? and query_hash = ? and query_mode = ? and observed_at >= ? "
            "order by observed_at desc, observation_id limit 1",
            (surface_id, query_hash, query_mode, observed_after),
        )

    def update_probe_job(
        self,
        *,
        probe_job_id: str,
        status: str,
        attempt_count: int,
        not_before: str,
        last_error_code: str | None,
    ) -> None:
        self._execute(
            """
            update probe_jobs
            set status = ?, attempt_count = ?, not_before = ?, last_error_code = ?
            where probe_job_id = ?
            """,
            (status, attempt_count, not_before, last_error_code, probe_job_id),
        )

    def pause_pending_probe_jobs(
        self,
        *,
        paused_status: str,
        error_code: str | None,
        exclude_probe_job_id: str,
    ) -> None:
        self._execute(
            """
            update probe_jobs
            set status = ?, last_error_code = ?
            where status in (?, ?) and probe_job_id != ?
            """,
            (
                paused_status,
                error_code,
                "scheduled",
                "retry_scheduled",
                exclude_probe_job_id,
            ),
        )

    def latest_successful_observation_total(self, surface_id: str) -> int | None:
        row = self._fetch_one(
            "select total from cts_recall_observations "
            "where surface_id = ? and status = ? and total is not null "
            "order by observed_at desc, observation_id limit 1",
            (surface_id, "ok"),
        )
        if row is None:
            return None
        return int(row["total"])

    def list_observations(self, surface_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from cts_recall_observations where surface_id = ? "
            "order by observed_at desc, observation_id",
            (surface_id,),
        )

    def list_review_decisions(
        self, target_type: str, target_id: str
    ) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from review_decisions where target_type = ? and target_id = ? "
            "order by reviewed_at, decision_id",
            (target_type, target_id),
        )

    def list_build_events(self, builder_run_id: str) -> list[dict[str, object]]:
        return self._fetch_all(
            "select * from build_events where builder_run_id = ? order by created_at, event_id",
            (builder_run_id,),
        )

    def _execute(self, sql: str, parameters: tuple[object, ...]) -> None:
        self.connection.execute(sql, parameters)
        self.connection.commit()

    def _fetch_one(
        self, sql: str, parameters: tuple[object, ...]
    ) -> dict[str, object] | None:
        row = self.connection.execute(sql, parameters).fetchone()
        if row is None:
            return None
        return dict(row)

    def _fetch_all(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[dict[str, object]]:
        return [dict(row) for row in self.connection.execute(sql, parameters).fetchall()]
