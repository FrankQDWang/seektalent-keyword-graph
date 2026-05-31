from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.builder.build_relations import build_relations
from seektalent_keyword_graph.builder.build_store import BuildStore


def test_vue_and_react_remain_separate_concepts_with_weak_cooccurrence_only(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface(store, surface_id="surface:vue", raw="Vue", norm="vue")
        _insert_surface(store, surface_id="surface:react", raw="React", norm="react")

        report = build_relations(store, builder_run_id="run-relations")

        assert report.concept_count == 2
        assert store.get_concept("concept:vue")["canonical_label"] == "Vue"
        assert store.get_concept("concept:react")["canonical_label"] == "React"
        assert store.list_surface_relations("surface:vue") == []

    finally:
        store.close()


def test_version_variant_relates_to_base_surface_without_replacing_it(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface(store, surface_id="surface:vue", raw="Vue", norm="vue")
        _insert_surface(store, surface_id="surface:vue 3", raw="Vue 3", norm="vue 3")

        report = build_relations(store, builder_run_id="run-relations")

        concept = store.get_concept("concept:vue")
        memberships = store.list_concept_surfaces("concept:vue")
        relation = store.list_surface_relations("surface:vue 3")[0]

        assert report.concept_count == 1
        assert concept["canonical_label"] == "Vue"
        assert concept["primary_surface_id"] == "surface:vue"
        assert {row["surface_id"] for row in memberships} == {
            "surface:vue",
            "surface:vue 3",
        }
        assert relation["from_surface_id"] == "surface:vue 3"
        assert relation["to_surface_id"] == "surface:vue"
        assert relation["relation_type"] == "version_variant"
        assert relation["evidence_type"] == "version_suffix"
        assert relation["status"] == "active"
        assert relation["created_by"] == "build_relations:v1"

    finally:
        store.close()


def _insert_surface(
    store: BuildStore,
    *,
    surface_id: str,
    raw: str,
    norm: str,
) -> None:
    now = "2026-05-31T00:00:00Z"
    store.insert_surface(
        surface_id=surface_id,
        text_raw=raw,
        text_norm=norm,
        display_text=raw,
        language="en",
        token_class="framework",
        query_safe=True,
        is_exact_phrase_preferred=" " in norm,
        ambiguity_score=0.1,
        specificity_score=0.9,
        jd_df=1,
        jd_tf_total=1,
        serving_status="active",
        created_at=now,
        updated_at=now,
    )
