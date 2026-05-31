from __future__ import annotations

import math
from pathlib import Path

import pytest

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.cooccurrence import build_cooccurrence_edges


def test_build_cooccurrence_edges_persists_deterministic_window_metrics(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_cooccurrence_fixture(store)

        report = build_cooccurrence_edges(store, builder_run_id="run-cooccur")

        assert report.edge_count == 18
        python_sql_jd = _edge(store, "surface:python", "surface:sql", "jd")
        assert python_sql_jd["cooccur_count"] == 2
        assert python_sql_jd["support"] == 2 / 3
        assert python_sql_jd["jaccard"] == 1.0
        assert python_sql_jd["pmi"] == pytest.approx(math.log2(1.5))

        python_sql_section = _edge(store, "surface:python", "surface:sql", "section")
        assert python_sql_section["cooccur_count"] == 2
        assert python_sql_section["support"] == 2 / 5
        assert python_sql_section["jaccard"] == 0.5
        assert python_sql_section["pmi"] == pytest.approx(math.log2(1.25))

        python_django_title_requirements = _edge(
            store,
            "surface:django",
            "surface:python",
            "title_plus_requirements",
        )
        assert python_django_title_requirements["cooccur_count"] == 1
        assert python_django_title_requirements["support"] == 1 / 3
        assert python_django_title_requirements["jaccard"] == 0.5
        assert python_django_title_requirements["pmi"] == pytest.approx(math.log2(1.5))
    finally:
        store.close()


def test_blocked_surfaces_do_not_create_serving_cooccurrence_edges(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_cooccurrence_fixture(store)

        build_cooccurrence_edges(store, builder_run_id="run-cooccur")

        blocked_edges = store.list_cooccurrence_edges("surface:acme")
        assert blocked_edges == []
    finally:
        store.close()


def _edge(
    store: BuildStore, surface_id_a: str, surface_id_b: str, window_type: str
) -> dict[str, object]:
    left, right = sorted((surface_id_a, surface_id_b))
    row = store.connection.execute(
        """
        select *
        from cooccurrence_edges
        where surface_id_a = ?
          and surface_id_b = ?
          and window_type = ?
        """,
        (left, right, window_type),
    ).fetchone()
    assert row is not None
    return dict(row)


def _insert_cooccurrence_fixture(store: BuildStore) -> None:
    now = "2026-05-31T00:00:00Z"
    _insert_document(store, "jd-1")
    _insert_document(store, "jd-2")
    _insert_document(store, "jd-3")
    _insert_section(store, "section:jd-1:title", "jd-1", "title", "Python Backend")
    _insert_section(
        store,
        "section:jd-1:requirements",
        "jd-1",
        "requirements",
        "Python Django SQL",
    )
    _insert_section(store, "section:jd-2:title", "jd-2", "title", "Python Data")
    _insert_section(
        store,
        "section:jd-2:requirements",
        "jd-2",
        "requirements",
        "Python SQL AWS",
    )
    _insert_section(store, "section:jd-3:title", "jd-3", "title", "Frontend")
    _insert_section(
        store,
        "section:jd-3:requirements",
        "jd-3",
        "requirements",
        "React Vue",
    )

    for raw, norm, jd_df, tf_total in (
        ("Python", "python", 2, 4),
        ("SQL", "sql", 2, 2),
        ("Django", "django", 1, 1),
        ("AWS", "aws", 1, 1),
        ("React", "react", 1, 1),
        ("Vue", "vue", 1, 1),
        ("Acme", "acme", 1, 1),
    ):
        store.insert_surface(
            surface_id=f"surface:{norm}",
            text_raw=raw,
            text_norm=norm,
            display_text=raw,
            language="en",
            token_class="tool",
            query_safe=norm != "acme",
            is_exact_phrase_preferred=False,
            ambiguity_score=0.1,
            specificity_score=0.9,
            jd_df=jd_df,
            jd_tf_total=tf_total,
            serving_status="blocked" if norm == "acme" else "active",
            created_at=now,
            updated_at=now,
        )

    mentions = [
        ("jd-1", "section:jd-1:title", "Python", "python"),
        ("jd-1", "section:jd-1:requirements", "Python", "python"),
        ("jd-1", "section:jd-1:requirements", "Django", "django"),
        ("jd-1", "section:jd-1:requirements", "SQL", "sql"),
        ("jd-1", "section:jd-1:requirements", "Acme", "acme"),
        ("jd-2", "section:jd-2:title", "Python", "python"),
        ("jd-2", "section:jd-2:requirements", "Python", "python"),
        ("jd-2", "section:jd-2:requirements", "SQL", "sql"),
        ("jd-2", "section:jd-2:requirements", "AWS", "aws"),
        ("jd-3", "section:jd-3:requirements", "React", "react"),
        ("jd-3", "section:jd-3:requirements", "Vue", "vue"),
    ]
    for index, (jd_id, section_id, raw, norm) in enumerate(mentions, 1):
        store.insert_keyword_mention(
            mention_id=f"mention:{index:03d}",
            jd_id=jd_id,
            section_id=section_id,
            surface_text_raw=raw,
            surface_text_norm=norm,
            mention_type="skill",
            requirement_strength="required",
            evidence_text=raw,
            start_offset=index,
            end_offset=index + len(raw),
            extractor_name="fixture",
            extractor_version="v1",
            confidence=0.9,
            review_status="pending",
        )
    store.insert_blocked_surface_candidate(
        candidate_id="blocked:acme",
        jd_id="jd-1",
        section_id="section:jd-1:requirements",
        surface_text_raw="Acme",
        surface_text_norm="acme",
        reason_code="company_like",
        evidence_text="Acme",
        extractor_name="fixture",
    )


def _insert_document(store: BuildStore, jd_id: str) -> None:
    store.insert_jd_document(
        jd_id=jd_id,
        source="fixture",
        source_ref=f"fixture://{jd_id}",
        title_raw="Fixture",
        jd_text_ref="inline",
        jd_text="Fixture",
        content_hash=f"hash:{jd_id}",
        language="en",
        captured_at="2026-05-31T00:00:00Z",
        created_at="2026-05-31T00:00:00Z",
        quality_flags_json="[]",
    )


def _insert_section(
    store: BuildStore,
    section_id: str,
    jd_id: str,
    section_type: str,
    text: str,
) -> None:
    store.insert_jd_section(
        section_id=section_id,
        jd_id=jd_id,
        section_type=section_type,
        text=text,
        start_offset=0,
        end_offset=len(text),
        confidence=0.95,
    )
