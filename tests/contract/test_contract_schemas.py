from __future__ import annotations

import json
from pathlib import Path

from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryPlanResponse

CONTRACT_DIR = Path("contracts/query-plan")


def _canonical_schema(model: type[QueryPlanRequest | QueryPlanResponse]) -> str:
    return json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"


def test_generated_request_schema_matches_committed_file_byte_for_byte() -> None:
    expected = (CONTRACT_DIR / "query-plan-request.schema.json").read_text()

    assert _canonical_schema(QueryPlanRequest) == expected


def test_generated_response_schema_matches_committed_file_byte_for_byte() -> None:
    expected = (CONTRACT_DIR / "query-plan-response.schema.json").read_text()

    assert _canonical_schema(QueryPlanResponse) == expected
