from seektalent_keyword_graph.builder.sections import split_sections


def test_split_requirement_section():
    sections = split_sections("岗位职责：负责平台建设。\n任职要求：熟悉 Python。")

    assert sections[0]["section_type"] == "responsibility"
    assert sections[1]["section_type"] == "requirement"
    assert sections[1]["text"] == "熟悉 Python。"
