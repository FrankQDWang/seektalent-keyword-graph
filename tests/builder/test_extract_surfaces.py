from seektalent_keyword_graph.builder.extract_surfaces import extract_surface_mentions


def test_extract_known_technical_terms():
    mentions = extract_surface_mentions("熟悉 Python 和 Kubernetes，了解 Spring Cloud。")
    texts = {mention["surface_text_raw"] for mention in mentions}

    assert {"Python", "Kubernetes", "Spring Cloud"} <= texts


def test_blocks_company_like_terms():
    mentions = extract_surface_mentions("熟悉 腾讯 云和 Python。")
    texts = {mention["surface_text_raw"] for mention in mentions}

    assert "Python" in texts
    assert "腾讯" not in texts
