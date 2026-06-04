"""Public runtime facade for keyword graph planning."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.config import KeywordGraphRuntimeSettings
from seektalent_keyword_graph.contracts import (
    QueryPlanRequest,
    QueryPlanResponse,
    QueryRecallRequest,
    QueryRecallResponse,
)
from seektalent_keyword_graph.runtime.bundled_snapshot import resolve_snapshot_location
from seektalent_keyword_graph.runtime.errors import SnapshotFormatError
from seektalent_keyword_graph.runtime.query_planner import QueryPlanner
from seektalent_keyword_graph.runtime.query_recall import QueryRecallOptimizer
from seektalent_keyword_graph.runtime.snapshot_store import SQLiteSnapshotStore


class KeywordGraph:
    """Keyword graph runtime facade."""

    def __init__(self, store: SQLiteSnapshotStore) -> None:
        self.store = store

    @classmethod
    def open(
        cls, snapshot_path: str | Path, manifest_path: str | Path | None = None
    ) -> KeywordGraph:
        return cls(SQLiteSnapshotStore.open(snapshot_path, manifest_path))

    @classmethod
    def open_from_settings(
        cls, settings: KeywordGraphRuntimeSettings
    ) -> KeywordGraph:
        if not settings.enabled:
            raise SnapshotFormatError(
                "keyword graph runtime is disabled by "
                "SEEKTALENT_KEYWORD_GRAPH_ENABLED"
            )
        location = resolve_snapshot_location(settings)
        return cls.open(location.snapshot_path, location.manifest_path)

    @classmethod
    def open_default(
        cls, environ: Mapping[str, str] | None = None
    ) -> KeywordGraph:
        return cls.open_from_settings(KeywordGraphRuntimeSettings.from_env(environ))

    def close(self) -> None:
        self.store.close()

    def build_query_plan(
        self, request: QueryPlanRequest | dict[str, Any]
    ) -> QueryPlanResponse:
        parsed_request = (
            request
            if isinstance(request, QueryPlanRequest)
            else QueryPlanRequest.model_validate(request)
        )
        return QueryPlanner(self.store).build(parsed_request)

    def analyze_query_recall(
        self, request: QueryRecallRequest | dict[str, Any]
    ) -> QueryRecallResponse:
        parsed_request = (
            request
            if isinstance(request, QueryRecallRequest)
            else QueryRecallRequest.model_validate(request)
        )
        return QueryRecallOptimizer(self.store).analyze(parsed_request)

    def optimize_query_terms(
        self, request: QueryRecallRequest | dict[str, Any]
    ) -> QueryRecallResponse:
        return self.analyze_query_recall(request)
