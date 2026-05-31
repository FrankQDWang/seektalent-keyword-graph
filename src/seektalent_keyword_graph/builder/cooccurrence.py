"""Compute and persist deterministic co-occurrence edges from build DB evidence."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations

from seektalent_keyword_graph.builder.build_store import BuildStore


@dataclass(frozen=True)
class CooccurrenceBuildReport:
    edge_count: int
    window_counts: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "edge_count": self.edge_count,
            "window_counts": self.window_counts,
        }


@dataclass(frozen=True)
class _Mention:
    jd_id: str
    section_id: str
    section_type: str
    surface_id: str


WINDOW_JD = "jd"
WINDOW_SECTION = "section"
WINDOW_TITLE_REQUIREMENTS = "title_plus_requirements"
WINDOW_TYPES = (WINDOW_JD, WINDOW_SECTION, WINDOW_TITLE_REQUIREMENTS)


def build_cooccurrence_edges(
    store: BuildStore, *, builder_run_id: str
) -> CooccurrenceBuildReport:
    """Build co-occurrence edges for active query-safe surfaces."""
    now = _utc_now()
    _ensure_builder_run(store, builder_run_id=builder_run_id, now=now)
    _clear_existing_edges(store)

    mentions = _load_serving_mentions(store)
    windows = {
        WINDOW_JD: _windows_by_jd(mentions),
        WINDOW_SECTION: _windows_by_section(mentions),
        WINDOW_TITLE_REQUIREMENTS: _windows_by_title_requirements(mentions),
    }

    edge_count = 0
    for window_type in WINDOW_TYPES:
        edge_count += _persist_window_edges(
            store,
            window_type=window_type,
            windows=windows[window_type],
            last_computed_at=now,
        )

    report = CooccurrenceBuildReport(
        edge_count=edge_count,
        window_counts={key: len(value) for key, value in windows.items()},
    )
    _upsert_build_event(
        store,
        event_id=f"event:{builder_run_id}:cooccurrence",
        builder_run_id=builder_run_id,
        event_type="build_cooccurrence",
        message="built co-occurrence edges",
        payload_json=json.dumps(report.as_dict(), sort_keys=True),
        created_at=now,
    )
    return report


def _load_serving_mentions(store: BuildStore) -> list[_Mention]:
    rows = store.connection.execute(
        """
        select
          mentions.jd_id,
          mentions.section_id,
          sections.section_type,
          surfaces.surface_id
        from keyword_mentions mentions
        join jd_sections sections
          on sections.section_id = mentions.section_id
        join surfaces
          on surfaces.text_norm = mentions.surface_text_norm
        where surfaces.serving_status = 'active'
          and surfaces.query_safe = 1
        order by mentions.jd_id, mentions.section_id, mentions.start_offset,
                 mentions.mention_id
        """
    ).fetchall()
    return [
        _Mention(
            jd_id=row["jd_id"],
            section_id=row["section_id"],
            section_type=row["section_type"],
            surface_id=row["surface_id"],
        )
        for row in rows
    ]


def _windows_by_jd(mentions: list[_Mention]) -> list[frozenset[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        grouped[mention.jd_id].add(mention.surface_id)
    return _ordered_windows(grouped)


def _windows_by_section(mentions: list[_Mention]) -> list[frozenset[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        grouped[mention.section_id].add(mention.surface_id)
    return _ordered_windows(grouped)


def _windows_by_title_requirements(mentions: list[_Mention]) -> list[frozenset[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for mention in mentions:
        if mention.section_type in {"title", "requirements"}:
            grouped[mention.jd_id].add(mention.surface_id)
    return _ordered_windows(grouped)


def _ordered_windows(grouped: dict[str, set[str]]) -> list[frozenset[str]]:
    return [
        frozenset(surfaces)
        for _, surfaces in sorted(grouped.items())
        if surfaces
    ]


def _persist_window_edges(
    store: BuildStore,
    *,
    window_type: str,
    windows: list[frozenset[str]],
    last_computed_at: str,
) -> int:
    if not windows:
        return 0

    total_windows = len(windows)
    surface_window_counts: Counter[str] = Counter()
    cooccurrence_counts: Counter[tuple[str, str]] = Counter()

    for window in windows:
        surface_window_counts.update(window)
        for left, right in combinations(sorted(window), 2):
            cooccurrence_counts[(left, right)] += 1

    for (left, right), count in sorted(cooccurrence_counts.items()):
        left_count = surface_window_counts[left]
        right_count = surface_window_counts[right]
        union_count = left_count + right_count - count
        support = count / total_windows
        jaccard = count / union_count
        pmi = math.log2(
            (count / total_windows)
            / ((left_count / total_windows) * (right_count / total_windows))
        )
        store.insert_cooccurrence_edge(
            edge_id=_edge_id(window_type, left, right),
            surface_id_a=left,
            surface_id_b=right,
            window_type=window_type,
            cooccur_count=count,
            pmi=pmi,
            jaccard=jaccard,
            support=support,
            last_computed_at=last_computed_at,
        )

    return len(cooccurrence_counts)


def _edge_id(window_type: str, left: str, right: str) -> str:
    digest = hashlib.sha256(f"{window_type}\0{left}\0{right}".encode()).hexdigest()[:16]
    return f"cooccur:{window_type}:{digest}"


def _clear_existing_edges(store: BuildStore) -> None:
    store.connection.execute("delete from cooccurrence_edges")
    store.connection.commit()


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
