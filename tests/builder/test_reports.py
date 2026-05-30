from seektalent_keyword_graph.builder.cooccurrence import count_cooccurrence
from seektalent_keyword_graph.builder.sampling_report import build_sampling_rows


def test_count_cooccurrence():
    docs = [{"surfaces": ["python", "kubernetes"]}, {"surfaces": ["python"]}]

    assert count_cooccurrence(docs)[("kubernetes", "python")] == 1


def test_sampling_rows_include_risk_reason():
    rows = build_sampling_rows([{"surface": "go", "risk": "ambiguous"}])

    assert rows[0]["surface"] == "go"
    assert rows[0]["risk"] == "ambiguous"
