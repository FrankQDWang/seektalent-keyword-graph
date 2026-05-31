"""Privacy marker scanning for releaseable snapshot artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_PRIVACY_MARKERS = (
    "KEYWORD_GRAPH_CTS_",
    "tenant_secret",
    "candidate_list",
    "candidate_id",
    "resume_text",
    ".env",
)


@dataclass(frozen=True)
class ForbiddenPrivacyMarker:
    marker: str


def scan_forbidden_markers(path: Path) -> list[ForbiddenPrivacyMarker]:
    """Scan artifact bytes for forbidden release markers."""
    text = path.read_bytes().decode("utf-8", errors="ignore")
    data = text.lower()
    findings: list[ForbiddenPrivacyMarker] = []
    for marker in FORBIDDEN_PRIVACY_MARKERS:
        if marker == "KEYWORD_GRAPH_CTS_":
            findings.extend(
                ForbiddenPrivacyMarker(marker=match.group(0))
                for match in re.finditer(r"KEYWORD_GRAPH_CTS_[A-Z0-9_]*", text)
            )
        elif marker.lower() in data:
            findings.append(ForbiddenPrivacyMarker(marker=marker))
    return findings
