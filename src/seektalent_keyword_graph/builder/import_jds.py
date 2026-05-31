"""Local JSONL JD import with dedupe and explicit bad-record reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.builder.build_store import BuildStore


@dataclass(frozen=True)
class ImportReport:
    imported_count: int
    duplicate_count: int
    error_count: int
    duplicates: list[dict[str, object]] = field(default_factory=list)
    errors: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "imported_count": self.imported_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
            "duplicates": self.duplicates,
            "errors": self.errors,
        }


def import_jsonl_jds(
    store: BuildStore, jsonl_path: str | Path, *, builder_run_id: str
) -> ImportReport:
    """Import local JD JSONL rows into the build DB."""
    imported = 0
    duplicates: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    seen_hashes: dict[str, str] = {}
    now = _utc_now()
    path = Path(jsonl_path)
    _ensure_builder_run(store, builder_run_id=builder_run_id, now=now)

    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append({"line_number": line_number, "reason": "malformed_json"})
            continue
        if not isinstance(row, dict):
            errors.append({"line_number": line_number, "reason": "not_object"})
            continue
        text = row.get("text")
        source_ref = str(row.get("source_ref", f"line-{line_number}"))
        if not isinstance(text, str):
            errors.append(
                {
                    "line_number": line_number,
                    "source_ref": source_ref,
                    "reason": "missing_text",
                }
            )
            continue
        normalized_text = text.strip()
        if not normalized_text:
            errors.append(
                {
                    "line_number": line_number,
                    "source_ref": source_ref,
                    "reason": "empty_text",
                }
            )
            continue
        content_hash = _content_hash(normalized_text)
        jd_id = _jd_id(content_hash)
        if content_hash in seen_hashes:
            duplicates.append(
                {
                    "line_number": line_number,
                    "source_ref": source_ref,
                    "duplicate_of_jd_id": seen_hashes[content_hash],
                }
            )
            continue
        seen_hashes[content_hash] = jd_id
        existing = store.connection.execute(
            "select jd_id from jd_documents where content_hash = ?", (content_hash,)
        ).fetchone()
        if existing is not None:
            duplicates.append(
                {
                    "line_number": line_number,
                    "source_ref": source_ref,
                    "duplicate_of_jd_id": existing["jd_id"],
                }
            )
            continue
        store.insert_jd_document(
            jd_id=jd_id,
            source=str(row.get("source", "jsonl")),
            source_ref=source_ref,
            title_raw=str(row.get("title", "")),
            jd_text_ref=str(row.get("jd_text_ref", "inline")),
            jd_text=normalized_text,
            content_hash=content_hash,
            language=detect_language(normalized_text),
            captured_at=_string_field(row, "captured_at", now),
            created_at=now,
            quality_flags_json=json.dumps(
                quality_flags(normalized_text), ensure_ascii=False
            ),
        )
        imported += 1

    report = ImportReport(
        imported_count=imported,
        duplicate_count=len(duplicates),
        error_count=len(errors),
        duplicates=duplicates,
        errors=errors,
    )
    _upsert_build_event(
        store,
        event_id=f"event:{builder_run_id}:import-jds",
        builder_run_id=builder_run_id,
        event_type="import_jds",
        message="imported local JSONL JDs",
        payload_json=json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True),
        created_at=now,
    )
    return report


def detect_language(text: str) -> str:
    chinese = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    if chinese and latin:
        return "zh" if chinese >= 10 else "mixed"
    if chinese:
        return "zh"
    return "en"


def quality_flags(text: str) -> list[str]:
    text_norm = text.casefold()
    flags: list[str] = []
    if any(marker in text_norm for marker in ("salary", "薪资", "50k", "30k")):
        flags.append("has_compensation")
    if any(marker in text_norm for marker in ("shanghai", "北京", "上海")):
        flags.append("has_location")
    if len(text.strip()) < 80:
        flags.append("short_text")
    return flags


def _content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _jd_id(content_hash: str) -> str:
    return "jd:" + content_hash.removeprefix("sha256:")[:16]


def _string_field(row: dict[str, Any], key: str, default: str) -> str:
    value = row.get(key, default)
    return value if isinstance(value, str) else default


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
