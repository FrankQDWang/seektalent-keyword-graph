from __future__ import annotations

from seektalent_keyword_graph.domain.classification import classify_surface


def test_go_is_ambiguous_and_not_promoted_over_golang() -> None:
    go = classify_surface("Go")
    golang = classify_surface("Golang")

    assert go.text_norm == "go"
    assert go.token_class == "language"
    assert go.ambiguity_score > golang.ambiguity_score
    assert go.specificity_score < golang.specificity_score
    assert "ambiguous_short_token" in go.rejection_reasons
    assert go.query_safe is False
    assert golang.query_safe is True


def test_company_department_and_generic_classifiers_produce_rejection_reasons() -> None:
    company = classify_surface("Acme AI")
    department = classify_surface("Data Platform Team")
    generic = classify_surface("Familiar")

    assert company.query_safe is False
    assert "company_like" in company.rejection_reasons
    assert department.query_safe is False
    assert "department_like" in department.rejection_reasons
    assert generic.query_safe is False
    assert "too_generic" in generic.rejection_reasons


def test_ai_method_surfaces_are_not_rejected_as_company_like() -> None:
    ai = classify_surface("AI")
    generative_ai = classify_surface("Generative AI")
    company = classify_surface("Acme AI")

    assert ai.token_class == "method"
    assert ai.query_safe is True
    assert "company_like" not in ai.rejection_reasons
    assert generative_ai.token_class == "method"
    assert generative_ai.query_safe is True
    assert "company_like" not in generative_ai.rejection_reasons
    assert company.query_safe is False
    assert "company_like" in company.rejection_reasons


def test_language_and_token_class_inference_for_mixed_technical_terms() -> None:
    classified = classify_surface("Java开发")

    assert classified.language == "mixed"
    assert classified.token_class == "mixed_technical"
    assert classified.query_safe is True
    assert classified.specificity_score > classified.ambiguity_score
