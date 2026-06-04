from __future__ import annotations

from seektalent_keyword_graph.domain.normalization import normalize_surface


def test_full_width_and_mixed_case_normalize_while_preserving_display_text() -> None:
    normalized = normalize_surface("  ＰｙＴｈｏｎ　３  ")

    assert normalized.text_norm == "python 3"
    assert normalized.display_text == "ＰｙＴｈｏｎ　３"
    assert normalized.search_text == "python 3"


def test_symbolic_technical_terms_survive_normalization() -> None:
    terms = {
        "C++": "c++",
        "Ｃ＃": "c#",
        ".NET": ".net",
        "Node.js": "node.js",
    }

    assert {term: normalize_surface(term).text_norm for term in terms} == terms


def test_chinese_english_mixed_tokens_keep_searchable_form() -> None:
    normalized = normalize_surface("  Java开发　工程师  ")

    assert normalized.text_norm == "java开发 工程师"
    assert normalized.search_text == "java开发 工程师"
    assert normalized.display_text == "Java开发　工程师"
