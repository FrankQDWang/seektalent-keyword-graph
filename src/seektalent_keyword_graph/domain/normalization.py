"""Surface normalization rules for stable lookup and display preservation."""

from __future__ import annotations

import re
import unicodedata

from seektalent_keyword_graph.domain.models import NormalizedSurface

_WHITESPACE = re.compile(r"\s+")


def normalize_surface(text: str) -> NormalizedSurface:
    """Normalize a raw surface with NFKC, casefolding, and whitespace collapse."""
    display_text = text.strip()
    nfkc = unicodedata.normalize("NFKC", text)
    text_norm = _WHITESPACE.sub(" ", nfkc.strip()).casefold()
    return NormalizedSurface(
        text_raw=text,
        display_text=display_text,
        text_norm=text_norm,
        search_text=text_norm,
    )
