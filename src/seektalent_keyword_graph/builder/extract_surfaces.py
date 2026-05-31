"""Persist JD sections, keyword mentions, surfaces, and blocked candidates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.extractors import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    Candidate,
    display_text,
    extract_candidates,
    surface_language,
)
from seektalent_keyword_graph.builder.sections import infer_strength, split_sections


@dataclass(frozen=True)
class ExtractionRunReport:
    jd_count: int
    section_count: int
    mention_count: int
    blocked_count: int
    surface_count: int
    failed_records: list[dict[str, object]]

    def as_dict(self) -> dict[str, object]:
        return {
            "jd_count": self.jd_count,
            "section_count": self.section_count,
            "mention_count": self.mention_count,
            "blocked_count": self.blocked_count,
            "surface_count": self.surface_count,
            "failed_records": self.failed_records,
        }


def extract_surfaces(store: BuildStore, *, builder_run_id: str) -> ExtractionRunReport:
    """Extract deterministic keyword evidence from imported JDs."""
    now = _utc_now()
    _ensure_builder_run(store, builder_run_id=builder_run_id, now=now)
    _delete_existing_extraction(store)
    jd_rows = store.connection.execute(
        "select * from jd_documents order by jd_id"
    ).fetchall()
    section_count = 0
    mention_count = 0
    blocked_count = 0
    failed_records: list[dict[str, object]] = []
    surface_evidence: dict[str, dict[str, object]] = {}

    for jd_row in jd_rows:
        jd_id = jd_row["jd_id"]
        try:
            sections = split_sections(jd_row["jd_text"], language=jd_row["language"])
            for section_index, section in enumerate(sections, 1):
                section_id = f"section:{jd_id}:{section_index:03d}"
                store.insert_jd_section(
                    section_id=section_id,
                    jd_id=jd_id,
                    section_type=section.section_type,
                    text=section.text,
                    start_offset=section.start_offset,
                    end_offset=section.end_offset,
                    confidence=section.confidence,
                )
                section_count += 1
                for candidate in extract_candidates(section.text):
                    if candidate.reason_code is None:
                        evidence_text = _local_evidence_text(
                            section.text, candidate.start_offset, candidate.end_offset
                        )
                        mention_count += _persist_mention(
                            store,
                            jd_id=jd_id,
                            section_id=section_id,
                            section_start=section.start_offset,
                            section_type=section.section_type,
                            evidence_text=evidence_text,
                            candidate=candidate,
                            mention_number=mention_count + 1,
                            evidence=surface_evidence,
                        )
                    else:
                        blocked_count += _persist_blocked(
                            store,
                            jd_id=jd_id,
                            section_id=section_id,
                            candidate=candidate,
                            blocked_number=blocked_count + 1,
                        )
                section_blocked = _blocked_candidate_for_section(
                    section_type=section.section_type,
                    section_text=section.text,
                    section_start=section.start_offset,
                )
                if section_blocked is not None:
                    blocked_count += _persist_blocked(
                        store,
                        jd_id=jd_id,
                        section_id=section_id,
                        candidate=section_blocked,
                        blocked_number=blocked_count + 1,
                    )
        except (KeyError, TypeError, ValueError) as exc:
            failed_records.append(
                {"jd_id": jd_id, "reason": exc.__class__.__name__, "message": str(exc)}
            )

    for text_norm, evidence in sorted(surface_evidence.items()):
        jd_ids = evidence["jd_ids"]
        raw_values = evidence["raw_values"]
        tf_total = evidence["tf_total"]
        display = display_text(list(raw_values))
        store.insert_surface(
            surface_id=f"surface:{text_norm}",
            text_raw=display,
            text_norm=text_norm,
            display_text=display,
            language=surface_language(display),
            token_class=str(evidence["token_class"]),
            query_safe=True,
            is_exact_phrase_preferred=" " in display,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=len(jd_ids),
            jd_tf_total=int(tf_total),
            serving_status="active",
            created_at=now,
            updated_at=now,
        )

    report = ExtractionRunReport(
        jd_count=len(jd_rows),
        section_count=section_count,
        mention_count=mention_count,
        blocked_count=blocked_count,
        surface_count=len(surface_evidence),
        failed_records=failed_records,
    )
    _upsert_build_event(
        store,
        event_id=f"event:{builder_run_id}:extract-surfaces",
        builder_run_id=builder_run_id,
        event_type="extract_surfaces",
        message="extracted keyword evidence",
        payload_json=json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True),
        created_at=now,
    )
    return report


def _persist_mention(
    store: BuildStore,
    *,
    jd_id: str,
    section_id: str,
    section_start: int,
    section_type: str,
    evidence_text: str,
    candidate: Candidate,
    mention_number: int,
    evidence: dict[str, dict[str, object]],
) -> int:
    start = section_start + candidate.start_offset
    end = section_start + candidate.end_offset
    store.insert_keyword_mention(
        mention_id=f"mention:{jd_id}:{mention_number:04d}",
        jd_id=jd_id,
        section_id=section_id,
        surface_text_raw=candidate.text,
        surface_text_norm=candidate.text_norm,
        mention_type=candidate.token_class,
        requirement_strength=infer_strength(section_type, evidence_text),
        evidence_text=evidence_text,
        start_offset=start,
        end_offset=end,
        extractor_name=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
        confidence=candidate.confidence,
        review_status="pending",
    )
    bucket = evidence.setdefault(
        candidate.text_norm,
        {
            "jd_ids": set(),
            "raw_values": set(),
            "tf_total": 0,
            "token_class": candidate.token_class,
        },
    )
    bucket["jd_ids"].add(jd_id)
    bucket["raw_values"].add(candidate.text)
    bucket["tf_total"] = int(bucket["tf_total"]) + 1
    return 1


def _local_evidence_text(text: str, start_offset: int, end_offset: int) -> str:
    line_start = text.rfind("\n", 0, start_offset) + 1
    line_end = text.find("\n", end_offset)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()


def _persist_blocked(
    store: BuildStore,
    *,
    jd_id: str,
    section_id: str,
    candidate: Candidate,
    blocked_number: int,
) -> int:
    store.insert_blocked_surface_candidate(
        candidate_id=f"blocked:{jd_id}:{blocked_number:04d}",
        jd_id=jd_id,
        section_id=section_id,
        surface_text_raw=candidate.text,
        surface_text_norm=candidate.text_norm,
        reason_code=str(candidate.reason_code),
        evidence_text=candidate.text,
        extractor_name=EXTRACTOR_NAME,
    )
    return 1


def _blocked_candidate_for_section(
    *, section_type: str, section_text: str, section_start: int
) -> Candidate | None:
    reason_by_section = {
        "company": "company_like",
        "department": "department_like",
        "location": "policy_blocked",
    }
    reason_code = reason_by_section.get(section_type)
    text = section_text.strip()
    if reason_code is None or not text:
        return None
    start_delta = section_text.index(text)
    return Candidate(
        text=text,
        text_norm=_normalize_blocked_surface(text),
        start_offset=section_start + start_delta,
        end_offset=section_start + start_delta + len(text),
        token_class="blocked",
        confidence=0.85,
        reason_code=reason_code,
    )


def _normalize_blocked_surface(text: str) -> str:
    from seektalent_keyword_graph.builder.extractors import normalize_surface

    return normalize_surface(text)


def _delete_existing_extraction(store: BuildStore) -> None:
    store.connection.execute("delete from blocked_surface_candidates")
    store.connection.execute("delete from keyword_mentions")
    store.connection.execute("delete from jd_sections")
    store.connection.execute("delete from surfaces")
    store.connection.commit()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ensure_builder_run(store: BuildStore, *, builder_run_id: str, now: str) -> None:
    existing = store.connection.execute(
        "select builder_run_id from builder_runs where builder_run_id = ?",
        (builder_run_id,),
    ).fetchone()
    if existing is None:
        store.insert_builder_run(
            builder_run_id=builder_run_id,
            started_at=now,
            input_corpus_version="local-jsonl",
            status="running",
            report_json="{}",
        )


def _upsert_build_event(
    store: BuildStore,
    *,
    event_id: str,
    builder_run_id: str,
    event_type: str,
    message: str,
    payload_json: str,
    created_at: str,
) -> None:
    store.connection.execute(
        """
        insert into build_events(
          event_id, builder_run_id, event_type, message, payload_json, created_at
        ) values (?, ?, ?, ?, ?, ?)
        on conflict(event_id) do update set
          event_type = excluded.event_type,
          message = excluded.message,
          payload_json = excluded.payload_json,
          created_at = excluded.created_at
        """,
        (event_id, builder_run_id, event_type, message, payload_json, created_at),
    )
    store.connection.commit()
