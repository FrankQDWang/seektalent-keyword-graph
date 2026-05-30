from seektalent_keyword_graph import QueryPlanRequest, QueryPlanResponse


def test_query_plan_request_defaults():
    request = QueryPlanRequest(
        request_id="req_001",
        seek_talent_run_id="run_001",
        job_title="Python backend engineer",
        jd_text="Need Python and Kubernetes.",
        requirement_terms=[{"text": "Python", "strength": "required"}],
    )

    assert request.schema_version == "query-plan-request-v1"
    assert request.kg_snapshot_id == "latest"
    assert request.max_query_bundles == 4


def test_query_plan_response_shape():
    response = QueryPlanResponse(
        request_id="req_001",
        kg_snapshot_id="kg_test",
        concept_sheet=[
            {
                "concept_id": "concept_python",
                "canonical_surface": "Python",
                "matched_surfaces": ["Python"],
                "evidence_codes": ["snapshot_surface_match"],
            }
        ],
        query_bundles=[
            {
                "bundle_id": "bundle_anchor_1",
                "bundle_type": "anchor",
                "priority": 1,
                "queries": [
                    {
                        "query_text": "Python",
                        "surfaces": ["surface_python"],
                        "expected_hit_count": 336708,
                        "confidence": 0.8,
                        "reason_codes": ["required_term", "snapshot_surface_match"],
                    }
                ],
            }
        ],
        rejected_surfaces=[
            {
                "surface_text": "Alibaba",
                "reason_code": "company_like",
                "source": "automatic_blocklist",
            }
        ],
        lineage={"input_hash": "sha256:test", "selection_policy_version": "policy-v1"},
        warnings=[{"code": "low_recall", "message": "Recall is below target"}],
    )

    dumped = response.model_dump()
    assert dumped["schema_version"] == "query-plan-response-v1"
    assert dumped["kg_snapshot_id"] == "kg_test"
    assert response.query_bundles[0].queries[0].query_text == "Python"
    assert response.concept_sheet[0].concept_id == "concept_python"
    assert response.rejected_surfaces[0].reason_code == "company_like"
    assert response.lineage.input_hash == "sha256:test"
    assert response.warnings[0].code == "low_recall"
