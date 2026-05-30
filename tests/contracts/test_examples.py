import json
from pathlib import Path

from seektalent_keyword_graph import QueryPlanRequest, QueryPlanResponse


def test_request_example_validates():
    data = json.loads(Path("contracts/query-plan/request.example.json").read_text())

    assert QueryPlanRequest.model_validate(data).request_id == "req_001"


def test_response_example_validates():
    data = json.loads(Path("contracts/query-plan/response.example.json").read_text())

    assert QueryPlanResponse.model_validate(data).kg_snapshot_id == "kg_fixture"
