import pytest

from seektalent_keyword_graph.cts.fake_client import FakeCtsCountClient


def test_fake_cts_success():
    client = FakeCtsCountClient({"Python": 336708})

    result = client.search_count("Python")

    assert result["total"] == 336708
    assert result["status"] == "success"


def test_fake_cts_timeout():
    client = FakeCtsCountClient({"timeout": "timeout"})

    with pytest.raises(TimeoutError):
        client.search_count("timeout")


def test_fake_cts_zero():
    client = FakeCtsCountClient({"RareTerm": 0})

    result = client.search_count("RareTerm")

    assert result["total"] == 0
    assert result["status"] == "success"


def test_fake_cts_rate_limited():
    client = FakeCtsCountClient({"Python": "rate_limited"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "rate_limited"


def test_fake_cts_api_error():
    client = FakeCtsCountClient({"Python": "api_error"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "api_error"


def test_fake_cts_auth_error():
    client = FakeCtsCountClient({"Python": "auth_error"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "auth_error"
