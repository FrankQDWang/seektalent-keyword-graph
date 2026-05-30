from seektalent_keyword_graph.cts.count_client import CtsCountClient


def test_cts_payload_uses_count_probe_page_size():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    assert client.build_payload("Python") == {
        "keyword": "Python",
        "page": 1,
        "pageSize": 1,
    }


def test_cts_response_parses_data_total_only():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    payload = {"data": {"total": 336708, "items": [{"id": "x"}]}}

    result = client.parse_response("Python", payload)

    assert result == {"query_text": "Python", "total": 336708, "status": "success"}


def test_cts_client_repr_hides_secret():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    rendered = repr(client)

    assert "tenant-secret" not in rendered
    assert "tenant-key" in rendered
