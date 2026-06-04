"""Public query plan request and response contracts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SchemaVersion = Literal["query-plan-request-v1", "query-plan-response-v1"]
RequirementStrength = Literal["required", "preferred", "nice_to_have"]
RequirementSource = Literal["requirement", "title", "jd_text", "notes"]
ConceptType = Literal[
    "skill",
    "platform",
    "language",
    "framework",
    "tool",
    "domain",
    "certificate",
    "method",
    "job_keyword",
    "qualification",
    "unknown",
]
RecallBucket = Literal["healthy", "too_wide", "too_narrow", "zero", "stale", "unknown"]
QueryMode = Literal["keyword", "exact", "phrase", "boolean"]
BundleType = Literal["anchor", "precision", "alias_probe", "exploration", "fallback"]
RejectedReasonCode = Literal[
    "company_like",
    "department_like",
    "too_generic",
    "zero_recall",
    "too_wide_without_companion",
    "stale_observation",
    "low_confidence_alias",
    "policy_blocked",
    "no_active_concept",
]
WarningCode = Literal[
    "no_match",
    "stale_observation",
    "unknown_observation",
    "fallback",
    "partial_snapshot",
]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ContractModel(BaseModel):
    """Base class for strict public contracts."""

    model_config = ConfigDict(extra="forbid")


class RequirementTerm(ContractModel):
    """A normalized incoming requirement surface from the consumer."""

    text: NonEmptyString
    strength: RequirementStrength = "required"
    source: RequirementSource = "requirement"


class ConceptSheetRow(ContractModel):
    """Resolved concept summary used by downstream consumers for explainability."""

    concept_id: NonEmptyString
    canonical_label: NonEmptyString
    concept_type: ConceptType
    requirement_strength: RequirementStrength
    matched_terms: list[NonEmptyString] = Field(min_length=1)
    selected_surfaces: list[NonEmptyString] = Field(min_length=1)
    recall_bucket: RecallBucket
    confidence: float = Field(ge=0.0, le=1.0)


class QueryPlanQuery(ContractModel):
    """One executable query surface inside a bundle."""

    query_text: NonEmptyString
    query_mode: QueryMode
    surfaces: list[NonEmptyString] = Field(min_length=1)
    reason: NonEmptyString
    priority: int = Field(ge=1)
    source_concept_ids: list[str]
    recall_bucket: RecallBucket


class QueryBundle(ContractModel):
    """A deterministic group of query recommendations with shared intent."""

    bundle_type: BundleType
    label: NonEmptyString
    queries: list[QueryPlanQuery] = Field(min_length=1)
    rationale: NonEmptyString
    priority: int = Field(ge=1)
    source_concept_ids: list[str]
    warnings: list[WarningCode] = Field(default_factory=list)


class RejectedSurface(ContractModel):
    """A candidate surface that was excluded before query construction."""

    surface_text: NonEmptyString
    normalized_surface: NonEmptyString
    reason_code: RejectedReasonCode
    source: RequirementSource
    evidence: NonEmptyString


class QueryPlanLineage(ContractModel):
    """Stable provenance for deterministic response replay and debugging."""

    input_hash: NonEmptyString
    snapshot_schema_version: Literal["snapshot-v1"]
    selection_policy_version: Literal["policy-v1"]
    source_refs: list[str]


class QueryPlanWarning(ContractModel):
    """Consumer-visible warning emitted by query planning."""

    code: WarningCode
    message: NonEmptyString
    source_terms: list[str] = Field(default_factory=list)


class QueryPlanRequest(ContractModel):
    """SeekTalent-to-keyword-graph query planning request."""

    schema_version: Literal["query-plan-request-v1"] = "query-plan-request-v1"
    request_id: NonEmptyString
    requirement_terms: list[RequirementTerm]
    title: str | None = None
    jd_text: str | None = None
    notes: list[str] = Field(default_factory=list)
    max_query_bundles: int = Field(default=5, ge=1, le=20)
    include_exploration: bool = True

    @model_validator(mode="after")
    def validate_has_input_source(self) -> QueryPlanRequest:
        has_requirement = bool(self.requirement_terms)
        has_title = bool(self.title and self.title.strip())
        has_jd_text = bool(self.jd_text and self.jd_text.strip())
        has_note = any(note.strip() for note in self.notes)

        if not (has_requirement or has_title or has_jd_text or has_note):
            raise ValueError(
                "request must include at least one non-blank requirement term, "
                "title, jd_text, or note"
            )

        return self


class QueryPlanResponse(ContractModel):
    """Keyword graph query planning response."""

    schema_version: Literal["query-plan-response-v1"]
    request_id: NonEmptyString
    kg_snapshot_id: NonEmptyString
    selection_policy_version: Literal["policy-v1"]
    concept_sheet: list[ConceptSheetRow]
    query_bundles: list[QueryBundle]
    rejected_surfaces: list[RejectedSurface]
    warnings: list[QueryPlanWarning]
    lineage: QueryPlanLineage
