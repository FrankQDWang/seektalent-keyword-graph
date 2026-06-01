"""Resolve query-plan request terms against a runtime snapshot."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from seektalent_keyword_graph.contracts import (
    QueryPlanRequest,
    RejectedSurface,
    RequirementSource,
    RequirementStrength,
)
from seektalent_keyword_graph.domain.classification import classify_surface
from seektalent_keyword_graph.domain.normalization import normalize_surface
from seektalent_keyword_graph.domain.policies import REJECTION_REASON_RANK
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore

_BLOCKING_REASON_CODES = {
    "company_like": "company_like",
    "department_like": "department_like",
    "too_generic": "too_generic",
}
_TERM_BOUNDARY = r"[0-9a-z+#]"


@dataclass(frozen=True)
class ResolvedTerm:
    text: str
    normalized_surface: str
    source: RequirementSource
    strength: RequirementStrength
    source_order: int
    surface: dict[str, Any]
    concept: dict[str, Any]
    confidence: float
    source_ref: str


@dataclass(frozen=True)
class UnmatchedTerm:
    text: str
    normalized_surface: str
    source: RequirementSource
    strength: RequirementStrength
    source_order: int
    source_ref: str


@dataclass(frozen=True)
class ResolvedInput:
    request: QueryPlanRequest
    matched_terms: list[ResolvedTerm]
    no_match_terms: list[UnmatchedTerm]
    rejected_surfaces: list[RejectedSurface]
    source_refs: list[str]


@dataclass(frozen=True)
class _CandidateTerm:
    text: str
    source: RequirementSource
    strength: RequirementStrength
    source_order: int
    source_ref: str


class ConceptResolver:
    """Normalize incoming terms and attach active snapshot concepts."""

    def __init__(self, store: SQLiteSnapshotStore) -> None:
        self.store = store

    def resolve(self, request: QueryPlanRequest) -> ResolvedInput:
        matched_by_norm: dict[str, ResolvedTerm] = {}
        no_match_by_norm: dict[str, UnmatchedTerm] = {}
        rejected_by_norm: dict[str, RejectedSurface] = {}
        source_refs: list[str] = []

        for candidate in self._candidate_terms(request):
            normalized = normalize_surface(candidate.text).text_norm
            if not normalized:
                continue
            source_refs.append(candidate.source_ref)
            classification = classify_surface(candidate.text)
            rejection_code = self._blocking_reason(classification.rejection_reasons)
            if rejection_code is not None:
                rejected_by_norm.setdefault(
                    normalized,
                    RejectedSurface(
                        surface_text=candidate.text,
                        normalized_surface=normalized,
                        reason_code=rejection_code,
                        source=candidate.source,
                        evidence=f"{candidate.text} classified as {rejection_code}.",
                    ),
                )
                continue

            surface = self.store.get_surface_by_norm(normalized)
            if surface is None:
                no_match_by_norm.setdefault(
                    normalized,
                    UnmatchedTerm(
                        text=candidate.text,
                        normalized_surface=normalized,
                        source=candidate.source,
                        strength=candidate.strength,
                        source_order=candidate.source_order,
                        source_ref=candidate.source_ref,
                    ),
                )
                continue

            concept_link = self._best_active_concept_link(str(surface["surface_id"]))
            if concept_link is None:
                rejected_by_norm.setdefault(
                    normalized,
                    RejectedSurface(
                        surface_text=candidate.text,
                        normalized_surface=normalized,
                        reason_code="no_active_concept",
                        source=candidate.source,
                        evidence="Matched active surface has no active concept link.",
                    ),
                )
                continue

            concept = self.store.get_concept(str(concept_link["concept_id"]))
            if concept is None:
                rejected_by_norm.setdefault(
                    normalized,
                    RejectedSurface(
                        surface_text=candidate.text,
                        normalized_surface=normalized,
                        reason_code="no_active_concept",
                        source=candidate.source,
                        evidence="Matched concept link references no active concept.",
                    ),
                )
                continue

            matched_by_norm.setdefault(
                normalized,
                ResolvedTerm(
                    text=candidate.text,
                    normalized_surface=normalized,
                    source=candidate.source,
                    strength=candidate.strength,
                    source_order=candidate.source_order,
                    surface=surface,
                    concept=concept,
                    confidence=float(concept_link["confidence"]),
                    source_ref=candidate.source_ref,
                ),
            )

        return ResolvedInput(
            request=request,
            matched_terms=sorted(
                matched_by_norm.values(),
                key=lambda term: (term.source_order, term.normalized_surface),
            ),
            no_match_terms=sorted(
                no_match_by_norm.values(),
                key=lambda term: (term.source_order, term.normalized_surface),
            ),
            rejected_surfaces=sorted(
                rejected_by_norm.values(),
                key=lambda rejection: (
                    REJECTION_REASON_RANK.get(rejection.reason_code, 99),
                    rejection.normalized_surface,
                ),
            ),
            source_refs=source_refs,
        )

    def _candidate_terms(self, request: QueryPlanRequest) -> list[_CandidateTerm]:
        candidates: list[_CandidateTerm] = []
        next_order = 0
        for term in request.requirement_terms:
            normalized = normalize_surface(term.text).text_norm
            candidates.append(
                _CandidateTerm(
                    text=term.text,
                    source=term.source,
                    strength=term.strength,
                    source_order=next_order,
                    source_ref=f"{term.source}:{normalized}",
                )
            )
            next_order += 1

        active_surfaces = self._active_surfaces_by_length()
        for source, text in self._free_text_sources(request):
            normalized_text = normalize_surface(text).text_norm
            matches: list[tuple[int, dict[str, Any]]] = []
            for surface in active_surfaces:
                normalized = str(surface["text_norm"])
                match_start = _surface_match_start(normalized_text, normalized)
                if match_start is None:
                    continue
                matches.append((match_start, surface))
            for _, surface in sorted(
                matches, key=lambda item: (item[0], str(item[1]["text_norm"]))
            ):
                normalized = str(surface["text_norm"])
                candidates.append(
                    _CandidateTerm(
                        text=str(surface["display_text"]),
                        source=source,
                        strength="preferred",
                        source_order=next_order,
                        source_ref=f"{source}:{normalized}",
                    )
                )
                next_order += 1
        return candidates

    def _free_text_sources(
        self, request: QueryPlanRequest
    ) -> list[tuple[RequirementSource, str]]:
        sources: list[tuple[RequirementSource, str]] = []
        if request.title and request.title.strip():
            sources.append(("title", request.title))
        if request.jd_text and request.jd_text.strip():
            sources.append(("jd_text", request.jd_text))
        sources.extend(("notes", note) for note in request.notes if note.strip())
        return sources

    def _active_surfaces_by_length(self) -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            """
            select * from surfaces
            where serving_status = 'active'
            order by length(text_norm) desc, text_norm
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _best_active_concept_link(self, surface_id: str) -> dict[str, Any] | None:
        for link in self.store.list_surface_concepts(surface_id):
            if str(link["status"]) == "active":
                return link
        return None

    def _blocking_reason(self, reasons: tuple[str, ...]) -> str | None:
        for reason in reasons:
            if reason in _BLOCKING_REASON_CODES:
                return _BLOCKING_REASON_CODES[reason]
        return None


def _contains_surface(text_norm: str, surface_norm: str) -> bool:
    return _surface_match_start(text_norm, surface_norm) is not None


def _surface_match_start(text_norm: str, surface_norm: str) -> int | None:
    pattern = rf"(?<!{_TERM_BOUNDARY}){re.escape(surface_norm)}(?!{_TERM_BOUNDARY})"
    match = re.search(pattern, text_norm)
    if match is None:
        return None
    return match.start()
