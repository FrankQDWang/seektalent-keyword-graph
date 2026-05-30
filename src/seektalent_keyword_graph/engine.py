from __future__ import annotations

from pathlib import Path
from typing import Any

from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryPlanResponse
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


class KeywordGraph:
    def __init__(self, snapshot: SQLiteSnapshot) -> None:
        self.snapshot = snapshot
        self.snapshot_path = snapshot.path

    @classmethod
    def open(cls, snapshot_path: str | Path) -> KeywordGraph:
        return cls(SQLiteSnapshot.open(snapshot_path))

    def lookup_surface(self, text: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from surfaces where text_norm = ? limit 1", (text.casefold(),)
        ).fetchone()
        return dict(row) if row else None

    def get_concept(self, concept_id: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from concepts where concept_id = ? limit 1", (concept_id,)
        ).fetchone()
        return dict(row) if row else None

    def build_query_plan(self, request: QueryPlanRequest) -> QueryPlanResponse:
        meta = self.snapshot.meta()
        bundles = []
        warnings = []
        for term in request.requirement_terms:
            surface = self.lookup_surface(term.text)
            if surface and surface["query_safe"]:
                bundles.append(
                    {
                        "bundle_id": "bundle_anchor_1",
                        "bundle_type": "anchor",
                        "priority": 1,
                        "queries": [
                            {
                                "query_text": surface["display_text"],
                                "surfaces": [surface["surface_id"]],
                                "expected_hit_count": surface["latest_cts_total"],
                                "confidence": 0.8,
                                "reason_codes": ["required_term", "snapshot_surface_match"],
                            }
                        ],
                    }
                )
                break
        if not bundles:
            bundles.append(
                {
                    "bundle_id": "bundle_fallback_1",
                    "bundle_type": "fallback",
                    "priority": 99,
                    "queries": [
                        {
                            "query_text": request.job_title,
                            "surfaces": [],
                            "confidence": 0.2,
                            "reason_codes": ["fallback_job_title"],
                        }
                    ],
                }
            )
            warnings.append({"code": "no_snapshot_surface_match"})
        return QueryPlanResponse(
            request_id=request.request_id,
            kg_snapshot_id=meta.get("kg_snapshot_id", request.kg_snapshot_id),
            concept_sheet=[],
            query_bundles=bundles,
            rejected_surfaces=[],
            lineage={
                "snapshot_schema_version": meta.get("snapshot_schema_version"),
                "selection_policy_version": meta.get("selection_policy_version"),
            },
            warnings=warnings,
        )
