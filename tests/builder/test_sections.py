from __future__ import annotations

from seektalent_keyword_graph.builder.sections import infer_strength, split_sections


def test_section_splitter_records_english_types_text_offsets_and_confidence() -> None:
    text = (
        "Intro text about the role.\n"
        "Requirements:\n"
        "Must have Python 3 and SQL.\n"
        "Preferred:\n"
        "Nice to have Kubernetes.\n"
    )

    sections = split_sections(text, language="en")

    assert [(section.section_type, section.text) for section in sections] == [
        ("description", "Intro text about the role."),
        ("requirements", "Must have Python 3 and SQL."),
        ("preferred", "Nice to have Kubernetes."),
    ]
    assert text[sections[1].start_offset : sections[1].end_offset] == sections[1].text
    assert sections[1].confidence == 0.95


def test_section_splitter_records_chinese_headings_and_paragraph_fallback() -> None:
    headed = (
        "岗位职责：\n负责 Vue 3 开发。\n任职要求：\n必须熟悉 TypeScript。\n"
        "加分项：\n优先考虑 Docker。"
    )
    fallback = "第一段 Python 3。\n\n第二段 Vue 3。"

    headed_sections = split_sections(headed, language="zh")
    fallback_sections = split_sections(fallback, language="zh")

    assert [section.section_type for section in headed_sections] == [
        "responsibilities",
        "requirements",
        "preferred",
    ]
    assert headed[
        headed_sections[1].start_offset : headed_sections[1].end_offset
    ] == "必须熟悉 TypeScript。"
    assert all(section.confidence == 0.95 for section in headed_sections)
    assert [section.section_type for section in fallback_sections] == [
        "description",
        "description",
    ]
    assert all(section.confidence == 0.5 for section in fallback_sections)


def test_requirement_strength_uses_section_and_local_markers() -> None:
    assert infer_strength("requirements", "Must have Python 3.") == "required"
    assert infer_strength("description", "熟悉 Spring Cloud 是必须条件。") == "required"
    assert infer_strength("preferred", "Nice to have Kubernetes.") == "preferred"
    assert infer_strength("description", "优先考虑熟悉 Docker。") == "preferred"
    assert infer_strength("responsibilities", "Build ML services.") == "mentioned"


def test_heading_parser_accepts_spaces_around_separators() -> None:
    english = "Requirements :\nMust have Redis.\nPreferred ：\nKafka is a plus."
    chinese = "任职要求 ：\n必须熟悉 Java 17。\n加分项 :\n优先考虑 Go。"

    english_types = [
        section.section_type for section in split_sections(english, language="en")
    ]
    chinese_types = [
        section.section_type for section in split_sections(chinese, language="zh")
    ]

    assert english_types == [
        "requirements",
        "preferred",
    ]
    assert chinese_types == [
        "requirements",
        "preferred",
    ]
