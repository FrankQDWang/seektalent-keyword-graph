"""Domain primitives for keyword graph building and runtime selection."""

from seektalent_keyword_graph.domain.classification import classify_surface
from seektalent_keyword_graph.domain.normalization import normalize_surface

__all__ = ["classify_surface", "normalize_surface"]
