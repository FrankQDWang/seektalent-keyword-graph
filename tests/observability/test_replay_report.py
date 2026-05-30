from seektalent_keyword_graph.observability.replay_report import summarize_replay


def test_summarize_replay():
    summary = summarize_replay(
        [
            {"warnings": []},
            {"warnings": [{"code": "no_snapshot_surface_match"}]},
        ]
    )

    assert summary["case_count"] == 2
    assert summary["warning_count"] == 1
