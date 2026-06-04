"""Generate deterministic CSV and JSONL sampling reports for review risks."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.builder.build_store import BuildStore

CSV_FIELDS = (
    "target_type",
    "target_id",
    "display_text",
    "risk_reason",
    "evidence_count",
    "proposed_action",
    "target_ids",
    "evidence",
)


@dataclass(frozen=True)
class SamplingReport:
    row_count: int
    csv_path: Path
    jsonl_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "row_count": self.row_count,
            "csv_path": str(self.csv_path),
            "jsonl_path": str(self.jsonl_path),
        }


@dataclass(frozen=True)
class SamplingRow:
    target_type: str
    target_id: str
    display_text: str
    risk_reason: str
    evidence_count: int
    proposed_action: str
    target_ids: list[str]
    evidence: list[dict[str, object]]

    def csv_record(self) -> dict[str, str]:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "display_text": self.display_text,
            "risk_reason": self.risk_reason,
            "evidence_count": str(self.evidence_count),
            "proposed_action": self.proposed_action,
            "target_ids": ";".join(self.target_ids),
            "evidence": json.dumps(
                self.evidence,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        }

    def json_record(self) -> dict[str, object]:
        return {
            "target_type": self.target_type,
            "target_id": self.target_id,
            "display_text": self.display_text,
            "risk_reason": self.risk_reason,
            "evidence_count": self.evidence_count,
            "proposed_action": self.proposed_action,
            "target_ids": self.target_ids,
            "evidence": self.evidence,
        }


def write_sampling_reports(
    store: BuildStore,
    *,
    csv_path: str | Path,
    jsonl_path: str | Path,
    builder_run_id: str,
) -> SamplingReport:
    """Write CSV and JSONL sampling reports from persisted builder risks."""
    now = _utc_now()
    _ensure_builder_run(store, builder_run_id=builder_run_id, now=now)
    rows = build_sampling_rows(store)

    resolved_csv_path = Path(csv_path)
    resolved_jsonl_path = Path(jsonl_path)
    resolved_csv_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    with resolved_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.csv_record())

    with resolved_jsonl_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row.json_record(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            handle.write("\n")

    report = SamplingReport(
        row_count=len(rows),
        csv_path=resolved_csv_path,
        jsonl_path=resolved_jsonl_path,
    )
    _upsert_build_event(
        store,
        event_id=f"event:{builder_run_id}:sampling-report",
        builder_run_id=builder_run_id,
        event_type="sampling_report",
        message="wrote sampling reports",
        payload_json=json.dumps(report.as_dict(), sort_keys=True),
        created_at=now,
    )
    return report


def build_sampling_rows(store: BuildStore) -> list[SamplingRow]:
    rows: list[SamplingRow] = []
    rows.extend(_ambiguous_surface_rows(store))
    rows.extend(_high_frequency_surface_rows(store))
    rows.extend(_weak_alias_rows(store))
    rows.extend(_company_blocker_rows(store))
    rows.extend(_concept_merge_rows(store))
    return rows


def _ambiguous_surface_rows(store: BuildStore) -> list[SamplingRow]:
    query_rows = store.connection.execute(
        """
        select surface_id, display_text, text_norm, ambiguity_score, jd_df, jd_tf_total
        from surfaces
        where serving_status = 'active'
          and ambiguity_score >= 0.8
        order by ambiguity_score desc, jd_df desc, surface_id
        """
    ).fetchall()
    return [
        SamplingRow(
            target_type="surface",
            target_id=row["surface_id"],
            display_text=row["display_text"],
            risk_reason="ambiguous_text",
            evidence_count=row["jd_tf_total"],
            proposed_action="review_surface",
            target_ids=[row["surface_id"]],
            evidence=[
                _compact_evidence(
                    text_norm=row["text_norm"],
                    ambiguity_score=row["ambiguity_score"],
                    jd_df=row["jd_df"],
                )
            ],
        )
        for row in query_rows
    ]


def _high_frequency_surface_rows(store: BuildStore) -> list[SamplingRow]:
    query_rows = store.connection.execute(
        """
        select surfaces.surface_id, surfaces.display_text, surfaces.text_norm,
               surfaces.jd_df, surfaces.jd_tf_total
        from surfaces
        left join concept_surfaces
          on concept_surfaces.surface_id = surfaces.surface_id
        where surfaces.serving_status = 'active'
          and surfaces.jd_df >= 5
          and concept_surfaces.surface_id is null
        order by surfaces.jd_df desc, surfaces.surface_id
        """
    ).fetchall()
    return [
        SamplingRow(
            target_type="surface",
            target_id=row["surface_id"],
            display_text=row["display_text"],
            risk_reason="high_frequency_new_surface",
            evidence_count=row["jd_df"],
            proposed_action="review_surface",
            target_ids=[row["surface_id"]],
            evidence=[
                _compact_evidence(
                    text_norm=row["text_norm"],
                    jd_df=row["jd_df"],
                    jd_tf_total=row["jd_tf_total"],
                )
            ],
        )
        for row in query_rows
    ]


def _weak_alias_rows(store: BuildStore) -> list[SamplingRow]:
    query_rows = store.connection.execute(
        """
        select relations.relation_id, relations.from_surface_id,
               relations.to_surface_id,
               relations.confidence, relations.evidence_type,
               source.display_text as source_display,
               target.display_text as target_display
        from surface_relations relations
        join surfaces source
          on source.surface_id = relations.from_surface_id
        join surfaces target
          on target.surface_id = relations.to_surface_id
        where relations.relation_type = 'alias'
          and relations.status = 'active'
          and relations.confidence < 0.75
        order by relations.confidence, relations.relation_id
        """
    ).fetchall()
    return [
        SamplingRow(
            target_type="relation",
            target_id=row["relation_id"],
            display_text=f"{row['source_display']} -> {row['target_display']}",
            risk_reason="weak_alias",
            evidence_count=1,
            proposed_action="review_relation",
            target_ids=[
                row["relation_id"],
                row["from_surface_id"],
                row["to_surface_id"],
            ],
            evidence=[
                _compact_evidence(
                    confidence=row["confidence"],
                    evidence_type=row["evidence_type"],
                )
            ],
        )
        for row in query_rows
    ]


def _company_blocker_rows(store: BuildStore) -> list[SamplingRow]:
    query_rows = store.connection.execute(
        """
        select candidate_id, surface_text_raw, surface_text_norm, reason_code,
               evidence_text
        from blocked_surface_candidates
        where reason_code = 'company_like'
        order by candidate_id
        """
    ).fetchall()
    return [
        SamplingRow(
            target_type="blocked_surface",
            target_id=row["candidate_id"],
            display_text=row["surface_text_raw"],
            risk_reason="company_like_blocker",
            evidence_count=1,
            proposed_action="confirm_block",
            target_ids=[row["candidate_id"]],
            evidence=[
                _compact_evidence(
                    text_norm=row["surface_text_norm"],
                    reason_code=row["reason_code"],
                    evidence_text=row["evidence_text"],
                )
            ],
        )
        for row in query_rows
    ]


def _concept_merge_rows(store: BuildStore) -> list[SamplingRow]:
    concept_rows = store.connection.execute(
        """
        select concept_id, canonical_label, surface_count, jd_df, stability_score,
               review_status
        from concepts
        where surface_count > 1
          and (
            review_status != 'approved'
            or stability_score < 0.75
          )
        order by stability_score, concept_id
        """
    ).fetchall()
    rows: list[SamplingRow] = []
    for concept in concept_rows:
        members = store.connection.execute(
            """
            select concept_surfaces.surface_id, concept_surfaces.confidence,
                   concept_surfaces.source, surfaces.display_text
            from concept_surfaces
            join surfaces
              on surfaces.surface_id = concept_surfaces.surface_id
            where concept_surfaces.concept_id = ?
            order by concept_surfaces.confidence, concept_surfaces.surface_id
            """,
            (concept["concept_id"],),
        ).fetchall()
        target_ids = [concept["concept_id"], *(row["surface_id"] for row in members)]
        rows.append(
            SamplingRow(
                target_type="concept_merge",
                target_id=concept["concept_id"],
                display_text=concept["canonical_label"],
                risk_reason="concept_merge_risk",
                evidence_count=len(members),
                proposed_action="review_merge",
                target_ids=target_ids,
                evidence=[
                    _compact_evidence(
                        surface_id=row["surface_id"],
                        display_text=row["display_text"],
                        confidence=row["confidence"],
                        source=row["source"],
                    )
                    for row in members
                ],
            )
        )
    return rows


def _compact_evidence(**values: Any) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


def _ensure_builder_run(store: BuildStore, *, builder_run_id: str, now: str) -> None:
    existing = store.connection.execute(
        "select builder_run_id from builder_runs where builder_run_id = ?",
        (builder_run_id,),
    ).fetchone()
    if existing is None:
        store.insert_builder_run(
            builder_run_id=builder_run_id,
            started_at=now,
            input_corpus_version="local-build-db",
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


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
