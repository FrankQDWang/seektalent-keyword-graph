"""Typed domain records shared by normalization, classification, and builders."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedSurface:
    text_raw: str
    display_text: str
    text_norm: str
    search_text: str


@dataclass(frozen=True)
class SurfaceClassification:
    text_raw: str
    text_norm: str
    language: str
    token_class: str
    query_safe: bool
    is_exact_phrase_preferred: bool
    ambiguity_score: float
    specificity_score: float
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RelationBuildReport:
    concept_count: int
    concept_surface_count: int
    relation_count: int
