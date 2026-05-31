from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.builder.build_relations import build_relations
from seektalent_keyword_graph.builder.build_store import BuildStore


def test_build_relations_persists_concepts_and_alias_evidence(tmp_path: Path) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface_with_mention(
            store,
            jd_id="jd-k8s",
            surface_id="surface:k8s",
            raw="k8s",
            norm="k8s",
            evidence_text="Kubernetes (k8s) production operations",
        )
        _insert_surface_with_mention(
            store,
            jd_id="jd-k8s",
            surface_id="surface:kubernetes",
            raw="Kubernetes",
            norm="kubernetes",
            evidence_text="Kubernetes (k8s) production operations",
        )

        report = build_relations(store, builder_run_id="run-relations")

        relations = store.list_surface_relations("surface:k8s")
        concepts = store.connection.execute("select * from concepts").fetchall()
        memberships = store.connection.execute(
            "select * from concept_surfaces order by surface_id"
        ).fetchall()

        assert report.concept_count == 1
        assert len(concepts) == 1
        assert concepts[0]["concept_id"] == "concept:kubernetes"
        assert concepts[0]["jd_df"] == 1
        assert {row["surface_id"] for row in memberships} == {
            "surface:k8s",
            "surface:kubernetes",
        }
        assert relations
        assert relations[0]["relation_type"] == "alias"
        assert relations[0]["confidence"] == 0.95
        assert relations[0]["evidence_type"] == "seed_alias_with_jd_evidence"
        assert relations[0]["status"] == "active"
        assert relations[0]["created_by"] == "build_relations:v1"
    finally:
        store.close()


def test_alias_seed_requires_relation_evidence_not_surface_existence_only(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface_with_mention(
            store,
            jd_id="jd-k8s",
            surface_id="surface:k8s",
            raw="k8s",
            norm="k8s",
            evidence_text="k8s cluster operations",
        )
        _insert_surface_with_mention(
            store,
            jd_id="jd-kubernetes",
            surface_id="surface:kubernetes",
            raw="Kubernetes",
            norm="kubernetes",
            evidence_text="Kubernetes platform experience",
        )

        report = build_relations(store, builder_run_id="run-relations")

        assert report.concept_count == 2
        assert store.list_surface_relations("surface:k8s") == []

    finally:
        store.close()


def test_query_unsafe_surface_is_skipped_without_safe_relation_evidence(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface_with_mention(
            store,
            jd_id="jd-go",
            surface_id="surface:go",
            raw="Go",
            norm="go",
            evidence_text="Go experience",
            token_class="language",
        )
        _insert_surface_with_mention(
            store,
            jd_id="jd-golang",
            surface_id="surface:golang",
            raw="Golang",
            norm="golang",
            evidence_text="Golang backend experience",
            token_class="language",
        )

        report = build_relations(store, builder_run_id="run-relations")

        concepts = {
            row["concept_id"]: row
            for row in store.connection.execute("select * from concepts").fetchall()
        }
        concept_surface_ids = {
            row["surface_id"]
            for row in store.connection.execute(
                "select surface_id from concept_surfaces"
            ).fetchall()
        }

        assert report.concept_count == 1
        assert "concept:go" not in concepts
        assert concepts["concept:golang"]["canonical_label"] == "Golang"
        assert "surface:go" not in concept_surface_ids
        assert "surface:golang" in concept_surface_ids

    finally:
        store.close()


def test_relation_ids_use_stable_safe_hash_not_raw_normalized_labels(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        _insert_surface_with_mention(
            store,
            jd_id="jd-special",
            surface_id="surface:node.js/api:v2",
            raw="Node.js/API:V2",
            norm="node.js/api:v2",
            evidence_text="Node.js/API:V2 and Node.js/API:V2 3",
        )
        _insert_surface_with_mention(
            store,
            jd_id="jd-special",
            surface_id="surface:node.js/api:v2 3",
            raw="Node.js/API:V2 3",
            norm="node.js/api:v2 3",
            evidence_text="Node.js/API:V2 and Node.js/API:V2 3",
        )

        build_relations(store, builder_run_id="run-relations")
        relation = store.list_surface_relations("surface:node.js/api:v2 3")[0]
        relation_id = relation["relation_id"]

        assert relation_id.startswith("relation:version_variant:")
        assert relation_id == "relation:version_variant:d362c9a851673b22"
        assert relation_id.count(":") == 2
        assert "/" not in relation_id
        assert "node.js" not in relation_id
        assert "api" not in relation_id

    finally:
        store.close()


def _insert_surface_with_mention(
    store: BuildStore,
    *,
    jd_id: str,
    surface_id: str,
    raw: str,
    norm: str,
    evidence_text: str,
    token_class: str = "tool",
) -> None:
    now = "2026-05-31T00:00:00Z"
    _ensure_jd(store, jd_id=jd_id, text=evidence_text, now=now)
    section_id = f"section:{jd_id}"
    if not store.list_sections(jd_id):
        store.insert_jd_section(
            section_id=section_id,
            jd_id=jd_id,
            section_type="requirements",
            text=evidence_text,
            start_offset=0,
            end_offset=len(evidence_text),
            confidence=0.95,
        )
    store.insert_keyword_mention(
        mention_id=f"mention:{jd_id}:{norm}",
        jd_id=jd_id,
        section_id=section_id,
        surface_text_raw=raw,
        surface_text_norm=norm,
        mention_type=token_class,
        requirement_strength="required",
        evidence_text=evidence_text,
        start_offset=0,
        end_offset=len(raw),
        extractor_name="test",
        extractor_version="v1",
        confidence=0.9,
        review_status="pending",
    )
    store.insert_surface(
        surface_id=surface_id,
        text_raw=raw,
        text_norm=norm,
        display_text=raw,
        language="en",
        token_class=token_class,
        query_safe=True,
        is_exact_phrase_preferred=False,
        ambiguity_score=0.1,
        specificity_score=0.9,
        jd_df=1,
        jd_tf_total=1,
        serving_status="active",
        created_at=now,
        updated_at=now,
    )


def _ensure_jd(store: BuildStore, *, jd_id: str, text: str, now: str) -> None:
    if store.get_jd_document(jd_id) is not None:
        return
    store.insert_jd_document(
        jd_id=jd_id,
        source="fixture",
        source_ref=f"fixture://{jd_id}",
        title_raw="Engineer",
        jd_text_ref="inline",
        jd_text=text,
        content_hash=f"hash:{jd_id}",
        language="en",
        captured_at=now,
        created_at=now,
        quality_flags_json="[]",
    )
