from seektalent_keyword_graph.domain.policies import recall_bucket


def test_recall_bucket_zero():
    assert recall_bucket(0) == "zero"


def test_recall_bucket_too_wide():
    assert recall_bucket(500000) == "too_wide"


def test_recall_bucket_healthy():
    assert recall_bucket(10000) == "healthy"
