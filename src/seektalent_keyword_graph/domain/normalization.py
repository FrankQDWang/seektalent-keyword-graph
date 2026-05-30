from __future__ import annotations

import unicodedata


def normalize_surface(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().casefold().split())
