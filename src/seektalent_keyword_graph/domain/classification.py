"""Conservative surface classification and query-safety heuristics."""

from __future__ import annotations

import re

from seektalent_keyword_graph.domain.models import SurfaceClassification
from seektalent_keyword_graph.domain.normalization import normalize_surface

_COMPANY_SUFFIX = re.compile(
    r"\b(?:inc|llc|ltd|corp|corporation|company|co|ai)\b", re.IGNORECASE
)
_DEPARTMENT_WORD = re.compile(
    r"\b(?:department|team|platform|engineering|业务|研发|算法|数据科学|团队)\b",
    re.IGNORECASE,
)
_VERSIONED = re.compile(r"^.+\s+\d+(?:\.\d+)*$")

_GENERIC_TERMS = {
    "familiar",
    "熟悉",
    "experience",
    "requirements",
    "required",
    "preferred",
    "team",
    "platform",
}

_LANGUAGES = {
    "c#",
    "c++",
    "go",
    "golang",
    "java",
    "java 17",
    "javascript",
    "python",
    "python 3",
    "sql",
    "typescript",
}

_FRAMEWORKS = {
    ".net",
    "node.js",
    "react",
    "spring cloud",
    "tensorflow",
    "tensorflow 2",
    "vue",
    "vue 3",
}

_TOOLS = {
    "aws",
    "ci/cd",
    "docker",
    "k8s",
    "kafka",
    "kubernetes",
    "redis",
    "s3",
}

_METHODS = {"ai", "generative ai", "machine learning", "rag", "llmops"}


def classify_surface(text: str) -> SurfaceClassification:
    """Classify a surface for builder persistence and query policy inputs."""
    normalized = normalize_surface(text)
    text_norm = normalized.text_norm
    language = _language(text_norm)
    token_class = _token_class(text_norm, language)
    rejection_reasons = _rejection_reasons(text_norm)
    ambiguity_score = _ambiguity_score(text_norm, rejection_reasons)
    specificity_score = _specificity_score(text_norm, token_class, rejection_reasons)
    query_safe = not rejection_reasons

    return SurfaceClassification(
        text_raw=text,
        text_norm=text_norm,
        language=language,
        token_class=token_class,
        query_safe=query_safe,
        is_exact_phrase_preferred=" " in text_norm or language == "mixed",
        ambiguity_score=ambiguity_score,
        specificity_score=specificity_score,
        rejection_reasons=tuple(rejection_reasons),
    )


def _language(text_norm: str) -> str:
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in text_norm)
    has_latin = any(char.isascii() and char.isalpha() for char in text_norm)
    if has_chinese and has_latin:
        return "mixed"
    if has_chinese:
        return "zh"
    return "en"


def _token_class(text_norm: str, language: str) -> str:
    if language == "mixed":
        return "mixed_technical"
    if text_norm in _LANGUAGES:
        return "language"
    if text_norm in _FRAMEWORKS:
        return "framework"
    if text_norm in _TOOLS:
        return "tool"
    if text_norm in _METHODS:
        return "method"
    if _VERSIONED.fullmatch(text_norm):
        return "versioned"
    if any(symbol in text_norm for symbol in ("+", "#", ".", "/")):
        return "technical"
    return "unknown"


def _rejection_reasons(text_norm: str) -> list[str]:
    reasons: list[str] = []
    if text_norm == "go":
        reasons.append("ambiguous_short_token")
    if _looks_company_like(text_norm):
        reasons.append("company_like")
    if _looks_department_like(text_norm):
        reasons.append("department_like")
    if text_norm in _GENERIC_TERMS:
        reasons.append("too_generic")
    return reasons


def _looks_company_like(text_norm: str) -> bool:
    return bool(_COMPANY_SUFFIX.search(text_norm)) and text_norm not in _METHODS


def _looks_department_like(text_norm: str) -> bool:
    return bool(_DEPARTMENT_WORD.search(text_norm)) and text_norm not in _FRAMEWORKS


def _ambiguity_score(text_norm: str, rejection_reasons: list[str]) -> float:
    score = 0.1
    if len(text_norm) <= 2:
        score += 0.35
    if "ambiguous_short_token" in rejection_reasons:
        score += 0.4
    if any(
        reason.endswith("_like") or reason == "too_generic"
        for reason in rejection_reasons
    ):
        score += 0.3
    return min(score, 1.0)


def _specificity_score(
    text_norm: str, token_class: str, rejection_reasons: list[str]
) -> float:
    score = 0.35
    if token_class in {"language", "framework", "tool", "method", "mixed_technical"}:
        score += 0.35
    if len(text_norm) >= 4:
        score += 0.15
    if " " in text_norm or any(symbol in text_norm for symbol in ("+", "#", ".", "/")):
        score += 0.1
    if rejection_reasons:
        score -= 0.35
    return max(0.0, min(score, 1.0))
