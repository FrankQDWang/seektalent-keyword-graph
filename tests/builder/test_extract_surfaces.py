from __future__ import annotations

from pathlib import Path

from seektalent_keyword_graph.builder.build_store import BuildStore
from seektalent_keyword_graph.builder.extract_surfaces import extract_surfaces
from seektalent_keyword_graph.builder.import_jds import import_jsonl_jds

FIXTURE = Path("tests/fixtures/jds/full_flow_jds.jsonl")


def test_extraction_persists_mentions_with_jd_section_evidence_lineage(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, FIXTURE, builder_run_id="run-extract")
        report = extract_surfaces(store, builder_run_id="run-extract")
        mention = store.connection.execute(
            """
            select m.*, s.section_type
            from keyword_mentions m
            join jd_sections s on s.section_id = m.section_id
            where m.surface_text_norm = 'python 3'
            """
        ).fetchone()

        assert report.mention_count >= 12
        assert mention is not None
        assert mention["jd_id"] == "jd:06bcfb9c3f854bbf"
        assert mention["section_id"].startswith("section:jd:06bcfb9c3f854bbf:")
        assert mention["section_type"] == "requirements"
        assert mention["requirement_strength"] == "required"
        assert mention["evidence_text"] == (
            "Must have Python 3, SQL, PyTorch and machine learning experience."
        )
        assert mention["start_offset"] >= 0
        assert mention["end_offset"] > mention["start_offset"]
    finally:
        store.close()


def test_extraction_persists_surfaces_from_evidence_counts_not_fixtures(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, FIXTURE, builder_run_id="run-extract")
        extract_surfaces(store, builder_run_id="run-extract")

        kubernetes = store.get_surface_by_norm("kubernetes")
        python = store.get_surface_by_norm("python 3")

        assert kubernetes is not None
        assert kubernetes["display_text"] == "Kubernetes"
        assert kubernetes["jd_df"] == 2
        assert kubernetes["jd_tf_total"] == 2
        assert python is not None
        assert python["jd_df"] == 1
        assert python["jd_tf_total"] == 1
        assert python["language"] == "en"
        assert python["token_class"] == "language"
        assert python["query_safe"] == 1
    finally:
        store.close()


def test_extraction_blocks_company_department_generic_and_policy_terms(
    tmp_path: Path,
) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, FIXTURE, builder_run_id="run-extract")
        extract_surfaces(store, builder_run_id="run-extract")
        blocked = store.connection.execute(
            """
            select surface_text_norm, reason_code
            from blocked_surface_candidates
            order by reason_code, surface_text_norm
            """
        ).fetchall()

        assert {(row["surface_text_norm"], row["reason_code"]) for row in blocked} >= {
            ("acme ai", "company_like"),
            ("星河科技", "company_like"),
            ("platform engineering", "department_like"),
            ("数据科学团队", "department_like"),
            ("familiar", "too_generic"),
            ("薪资 30k-45k", "policy_blocked"),
            ("shanghai", "policy_blocked"),
            ("北京", "policy_blocked"),
        }
        assert store.get_surface_by_norm("acme ai") is None
        assert store.get_surface_by_norm("shanghai") is None
    finally:
        store.close()


def test_extraction_generalizes_blockers_beyond_fixture_literals(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "generalized_blockers.jsonl"
    fixture.write_text(
        "\n".join(
            [
                '{"source":"fixture","source_ref":"general","title":"Data Role",'
                '"text":"Company: Globex Inc\\nDepartment: Data Platform\\n'
                'Requirements:\\nMust know Redis. Remote in 北京/上海.",'
                '"captured_at":"2026-05-31T00:00:00Z"}'
            ]
        ),
        encoding="utf-8",
    )
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, fixture, builder_run_id="run-general")
        extract_surfaces(store, builder_run_id="run-general")
        blocked = {
            (row["surface_text_norm"], row["reason_code"])
            for row in store.connection.execute(
                "select surface_text_norm, reason_code from blocked_surface_candidates"
            ).fetchall()
        }

        assert ("globex inc", "company_like") in blocked
        assert ("data platform", "department_like") in blocked
        assert ("remote", "policy_blocked") in blocked
        assert ("北京/上海", "policy_blocked") in blocked
    finally:
        store.close()


def test_extraction_blocks_generalized_location_sections(tmp_path: Path) -> None:
    fixture = tmp_path / "locations.jsonl"
    fixture.write_text(
        "\n".join(
            [
                '{"source":"fixture","source_ref":"location-en","title":"SRE",'
                '"text":"Location: Hangzhou\\nRequirements:\\nMust know Kubernetes.",'
                '"captured_at":"2026-05-31T00:00:00Z"}',
                '{"source":"fixture","source_ref":"location-zh","title":"平台工程师",'
                '"text":"地点：杭州\\n任职要求：\\n必须熟悉 Redis。",'
                '"captured_at":"2026-05-31T00:00:00Z"}',
            ]
        ),
        encoding="utf-8",
    )
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, fixture, builder_run_id="run-locations")
        extract_surfaces(store, builder_run_id="run-locations")
        blocked = {
            (row["surface_text_norm"], row["reason_code"])
            for row in store.connection.execute(
                "select surface_text_norm, reason_code from blocked_surface_candidates"
            ).fetchall()
        }

        assert ("hangzhou", "policy_blocked") in blocked
        assert ("杭州", "policy_blocked") in blocked
        assert store.get_surface_by_norm("hangzhou") is None
        assert store.get_surface_by_norm("杭州") is None
    finally:
        store.close()


def test_extraction_finds_non_fixture_technical_tokens_in_mixed_jds(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "generalized_terms.jsonl"
    fixture.write_text(
        "\n".join(
            [
                '{"source":"fixture","source_ref":"terms-en","title":"Backend",'
                '"text":"Requirements :\\nMust know Redis, Kafka, TensorFlow 2, '
                'Java 17 and Go.",'
                '"captured_at":"2026-05-31T00:00:00Z"}',
                '{"source":"fixture","source_ref":"terms-zh","title":"算法工程师",'
                '"text":"任职要求 ：\\n必须熟悉 Redis、Kafka、'
                'TensorFlow 2、Java 17 和 Go。",'
                '"captured_at":"2026-05-31T00:00:00Z"}',
            ]
        ),
        encoding="utf-8",
    )
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, fixture, builder_run_id="run-terms")
        extract_surfaces(store, builder_run_id="run-terms")

        surfaces = {
            row["text_norm"]: row["token_class"]
            for row in store.connection.execute(
                "select text_norm, token_class from surfaces"
            ).fetchall()
        }

        assert surfaces.items() >= {
            "redis": "tool",
            "kafka": "tool",
            "tensorflow 2": "framework",
            "java 17": "language",
            "go": "language",
        }.items()
    finally:
        store.close()


def test_extraction_uses_mixed_technical_token_patterns_without_noise(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "mixed_patterns.jsonl"
    fixture.write_text(
        "\n".join(
            [
                '{"source":"fixture","source_ref":"mixed-patterns","title":"AI 平台",'
                '"text":"Company: Globex Inc\\nDepartment: Data Platform\\nLocation: '
                'Hangzhou\\nRequirements:\\n必须熟悉 LLMOps、RAG、CI/CD、S3 '
                '和 Kubernetes。'
                '\\nRemote allowed. Salary 40k-60k.",'
                '"captured_at":"2026-05-31T00:00:00Z"}'
            ]
        ),
        encoding="utf-8",
    )
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, fixture, builder_run_id="run-patterns")
        extract_surfaces(store, builder_run_id="run-patterns")

        surfaces = {
            row["text_norm"]: row["token_class"]
            for row in store.connection.execute(
                "select text_norm, token_class from surfaces"
            ).fetchall()
        }
        blocked = {
            row["surface_text_norm"]
            for row in store.connection.execute(
                "select surface_text_norm from blocked_surface_candidates"
            ).fetchall()
        }

        assert surfaces.items() >= {
            "llmops": "tool",
            "rag": "method",
            "ci/cd": "tool",
            "s3": "platform",
            "kubernetes": "tool",
        }.items()
        assert blocked >= {
            "globex inc",
            "data platform",
            "hangzhou",
            "remote",
            "salary 40k-60k",
        }
        assert not {
            "must",
            "familiar",
            "remote",
            "globex inc",
            "data platform",
            "salary 40k-60k",
            "hangzhou",
        } & surfaces.keys()
    finally:
        store.close()


def test_extract_surfaces_is_idempotent_for_same_builder_run(tmp_path: Path) -> None:
    store = BuildStore.open(tmp_path / "build.sqlite3")
    try:
        import_jsonl_jds(store, FIXTURE, builder_run_id="run-extract")
        first_report = extract_surfaces(store, builder_run_id="run-extract")
        second_report = extract_surfaces(store, builder_run_id="run-extract")

        assert second_report == first_report
        section_count = store.connection.execute(
            "select count(*) from jd_sections"
        ).fetchone()[0]
        mention_count = store.connection.execute(
            "select count(*) from keyword_mentions"
        ).fetchone()[0]
        surface_count = store.connection.execute(
            "select count(*) from surfaces"
        ).fetchone()[0]
        assert section_count == 11
        assert mention_count == 15
        assert surface_count == 14
        assert (
            len(
                [
                    event
                    for event in store.list_build_events("run-extract")
                    if event["event_type"] == "extract_surfaces"
                ]
            )
            == 1
        )
    finally:
        store.close()
