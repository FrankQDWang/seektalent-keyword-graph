from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequirementTerm(BaseModel):
    text: str
    strength: Literal["required", "preferred", "nice_to_have", "unknown"] = "unknown"


class ConceptSheetRow(BaseModel):
    concept_id: str
    canonical_surface: str
    matched_surfaces: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)


class QueryPlanQuery(BaseModel):
    query_text: str
    surfaces: list[str] = Field(default_factory=list)
    expected_hit_count: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)


class QueryBundle(BaseModel):
    bundle_id: str
    bundle_type: Literal["anchor", "precision", "alias_probe", "exploration", "fallback"]
    priority: int = Field(ge=1)
    queries: list[QueryPlanQuery] = Field(default_factory=list)


class RejectedSurface(BaseModel):
    surface_text: str
    reason_code: str
    source: str = "runtime"


class QueryPlanLineage(BaseModel):
    input_hash: str | None = None
    snapshot_schema_version: str | None = None
    selection_policy_version: str | None = None


class QueryPlanWarning(BaseModel):
    code: str
    message: str = ""
    severity: Literal["info", "warning", "error"] = "warning"


class QueryPlanRequest(BaseModel):
    schema_version: Literal["query-plan-request-v1"] = "query-plan-request-v1"
    request_id: str
    seek_talent_run_id: str | None = None
    kg_snapshot_id: str = "latest"
    job_title: str
    jd_text: str = ""
    notes: str = ""
    requirement_terms: list[RequirementTerm] = Field(default_factory=list)
    max_query_bundles: int = Field(default=4, ge=1, le=20)


class QueryPlanResponse(BaseModel):
    schema_version: Literal["query-plan-response-v1"] = "query-plan-response-v1"
    request_id: str
    kg_snapshot_id: str
    concept_sheet: list[ConceptSheetRow] = Field(default_factory=list)
    query_bundles: list[QueryBundle] = Field(default_factory=list)
    rejected_surfaces: list[RejectedSurface] = Field(default_factory=list)
    lineage: QueryPlanLineage = Field(default_factory=QueryPlanLineage)
    warnings: list[QueryPlanWarning] = Field(default_factory=list)
