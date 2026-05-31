"""Deterministic keyword and blocked-candidate extraction rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

EXTRACTOR_NAME = "deterministic_rules"
EXTRACTOR_VERSION = "v1"


@dataclass(frozen=True)
class Candidate:
    text: str
    text_norm: str
    start_offset: int
    end_offset: int
    token_class: str
    confidence: float
    reason_code: str | None = None


SURFACE_SPECS = (
    ("AWS Certified Solutions Architect", "certificate"),
    ("Spring Cloud", "framework"),
    ("TensorFlow 2", "framework"),
    ("machine learning", "method"),
    ("TypeScript", "language"),
    ("JavaScript", "language"),
    ("Kubernetes", "tool"),
    ("Java 17", "language"),
    ("Node.js", "framework"),
    ("Python 3", "language"),
    ("PyTorch", "framework"),
    ("Redis", "tool"),
    ("Kafka", "tool"),
    ("Docker", "tool"),
    ("React", "framework"),
    ("Spark", "framework"),
    ("Vue 3", "framework"),
    ("SQL", "language"),
    ("Go", "language"),
)

BLOCKED_PATTERNS = (
    (
        re.compile(r"(?:数据科学|算法|研发|工程|平台|产品|业务)[\u4e00-\u9fffA-Za-z]*团队"),
        "department_like",
    ),
    (re.compile(r"\bFamiliar\b", re.IGNORECASE), "too_generic"),
    (re.compile(r"(?<!优先考虑)熟悉"), "too_generic"),
    (re.compile(r"\bsalary\s+\d+k-\d+k\b", re.IGNORECASE), "policy_blocked"),
    (re.compile(r"薪资\s*\d+k-\d+k", re.IGNORECASE), "policy_blocked"),
    (re.compile(r"\bremote\b", re.IGNORECASE), "policy_blocked"),
    (
        re.compile(r"\b(?:Beijing|Shanghai|Shenzhen|Guangzhou)\b", re.IGNORECASE),
        "policy_blocked",
    ),
    (
        re.compile(r"(?:北京|上海|深圳|广州)(?:\s*/\s*(?:北京|上海|深圳|广州))*"),
        "policy_blocked",
    ),
)

TECHNICAL_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9#])"
    r"(?:"
    r"[A-Z][A-Za-z0-9]*(?:Ops|DB|SQL|ML|AI)"
    r"|[A-Z]{2,}(?:/[A-Z]{2,})+"
    r"|[A-Z]{2,}\d*"
    r"|[A-Z][a-zA-Z]+(?:-[A-Z][a-zA-Z0-9]+)+"
    r"|[A-Z][A-Za-z]+(?:\s+\d+)"
    r"|[A-Z]\d"
    r")"
    r"(?![A-Za-z0-9#])"
)

STOP_TECHNICAL_TOKENS = {
    "ai",
    "company",
    "department",
    "familiar",
    "hangzhou",
    "location",
    "must",
    "remote",
    "requirements",
    "salary",
}


def extract_candidates(text: str) -> list[Candidate]:
    candidates: list[Candidate] = []
    for surface, token_class in SURFACE_SPECS:
        pattern = _surface_pattern(surface)
        for match in pattern.finditer(text):
            candidates.append(
                Candidate(
                    text=match.group(0),
                    text_norm=normalize_surface(match.group(0)),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    token_class=token_class,
                    confidence=0.9,
                )
            )
    existing_spans = [
        (candidate.start_offset, candidate.end_offset)
        for candidate in candidates
        if candidate.reason_code is None
    ]
    for match in TECHNICAL_TOKEN_PATTERN.finditer(text):
        if _span_overlaps(match.span(), existing_spans):
            continue
        token = match.group(0)
        token_norm = normalize_surface(token)
        if token_norm in STOP_TECHNICAL_TOKENS or _looks_like_policy_value(token_norm):
            continue
        candidates.append(
            Candidate(
                text=token,
                text_norm=token_norm,
                start_offset=match.start(),
                end_offset=match.end(),
                token_class=_technical_token_class(token_norm),
                confidence=0.75,
            )
        )
    for pattern, reason_code in BLOCKED_PATTERNS:
        for match in pattern.finditer(text):
            candidates.append(
                Candidate(
                    text=match.group(0),
                    text_norm=normalize_surface(match.group(0)),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    token_class="blocked",
                    confidence=0.8,
                    reason_code=reason_code,
                )
            )
    return sorted(
        candidates, key=lambda candidate: (candidate.start_offset, candidate.text_norm)
    )


def normalize_surface(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized.casefold()


def surface_language(text: str) -> str:
    has_chinese = any("\u4e00" <= char <= "\u9fff" for char in text)
    has_latin = any(char.isascii() and char.isalpha() for char in text)
    if has_chinese and has_latin:
        return "mixed"
    if has_chinese:
        return "zh"
    return "en"


def display_text(raw_values: list[str]) -> str:
    return sorted(raw_values, key=lambda value: (-len(value), value.casefold()))[0]


def _surface_pattern(surface: str) -> re.Pattern[str]:
    escaped = re.escape(surface).replace(r"\ ", r"\s+")
    if surface[0].isascii() and surface[-1].isascii():
        return re.compile(rf"(?<![A-Za-z0-9#]){escaped}(?![A-Za-z0-9#])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _span_overlaps(span: tuple[int, int], existing: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(
        start < existing_end and end > existing_start
        for existing_start, existing_end in existing
    )


def _looks_like_policy_value(token_norm: str) -> bool:
    return bool(re.fullmatch(r"\d+k-\d+k", token_norm))


def _technical_token_class(token_norm: str) -> str:
    if "/" in token_norm or token_norm.endswith("ops"):
        return "tool"
    if token_norm in {"rag", "ml", "ai"}:
        return "method"
    if re.fullmatch(r"[a-z]\d", token_norm):
        return "platform"
    if re.search(r"\s+\d+$", token_norm):
        return "language"
    return "unknown"
