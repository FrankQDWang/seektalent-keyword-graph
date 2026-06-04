"""JD section splitting and requirement strength hints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JDSection:
    section_type: str
    text: str
    start_offset: int
    end_offset: int
    confidence: float


HEADING_TYPES = {
    "company": "company",
    "公司": "company",
    "department": "department",
    "部门": "department",
    "requirements": "requirements",
    "requirement": "requirements",
    "任职要求": "requirements",
    "职位要求": "requirements",
    "preferred": "preferred",
    "加分项": "preferred",
    "优先条件": "preferred",
    "responsibilities": "responsibilities",
    "岗位职责": "responsibilities",
    "工作职责": "responsibilities",
    "benefits": "benefits",
    "福利": "benefits",
    "location": "location",
    "地点": "location",
}

REQUIRED_MARKERS = (
    "must",
    "required",
    "requirement",
    "必须",
    "必备",
    "要求",
    "熟悉",
)
PREFERRED_MARKERS = ("nice to have", "preferred", "plus", "优先", "加分")


def split_sections(text: str, *, language: str) -> list[JDSection]:
    """Split a JD into typed sections with source offsets."""
    headings = _find_headings(text)
    if headings:
        return _sections_from_headings(text, headings)
    return _paragraph_sections(text, language=language)


def infer_strength(section_type: str, evidence_text: str) -> str:
    """Infer whether a keyword mention is required, preferred, or merely mentioned."""
    evidence_norm = evidence_text.casefold()
    if section_type == "preferred" or any(
        marker in evidence_norm for marker in PREFERRED_MARKERS
    ):
        return "preferred"
    if section_type == "requirements" or any(
        marker in evidence_norm for marker in REQUIRED_MARKERS
    ):
        return "required"
    return "mentioned"


def _find_headings(text: str) -> list[tuple[int, int, str]]:
    headings: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        heading_text, separator, _content = stripped.partition(":")
        if not separator:
            heading_text, separator, _content = stripped.partition("：")
        if not separator and stripped.endswith((".", "。")):
            offset += len(line)
            continue
        key = (heading_text if separator else stripped.rstrip(":：")).strip().casefold()
        section_type = HEADING_TYPES.get(key)
        if section_type is not None:
            heading_start = offset + line.index(stripped)
            if separator:
                content_start = heading_start + len(heading_text) + len(separator)
            else:
                content_start = heading_start + len(stripped)
            headings.append((heading_start, content_start, section_type))
        offset += len(line)
    return headings


def _sections_from_headings(
    text: str, headings: list[tuple[int, int, str]]
) -> list[JDSection]:
    sections: list[JDSection] = []
    for index, (_heading_start, content_start, section_type) in enumerate(headings):
        next_start = headings[index + 1][0] if index + 1 < len(headings) else len(text)
        content_start, content_end = _trim_span(text, content_start, next_start)
        if content_start < content_end:
            sections.append(
                JDSection(
                    section_type=section_type,
                    text=text[content_start:content_end],
                    start_offset=content_start,
                    end_offset=content_end,
                    confidence=0.95,
                )
            )
    first_heading_start = headings[0][0]
    intro_start, intro_end = _trim_span(text, 0, first_heading_start)
    if intro_start < intro_end:
        sections.insert(
            0,
            JDSection(
                section_type="description",
                text=text[intro_start:intro_end],
                start_offset=intro_start,
                end_offset=intro_end,
                confidence=0.75,
            ),
        )
    return sections


def _paragraph_sections(text: str, *, language: str) -> list[JDSection]:
    sections: list[JDSection] = []
    cursor = 0
    for paragraph in text.split("\n\n"):
        raw_start = cursor
        raw_end = cursor + len(paragraph)
        start, end = _trim_span(text, raw_start, raw_end)
        if start < end:
            sections.append(
                JDSection(
                    section_type="description",
                    text=text[start:end],
                    start_offset=start,
                    end_offset=end,
                    confidence=0.5 if language in {"en", "zh", "mixed"} else 0.4,
                )
            )
        cursor = raw_end + 2
    return sections


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if start < end and text[start] in {":", "："}:
        start += 1
    while start < end and text[start].isspace():
        start += 1
    return start, end
