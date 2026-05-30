def test_package_imports():
    import seektalent_keyword_graph

    assert seektalent_keyword_graph.__version__ == "0.1.0"
    assert hasattr(seektalent_keyword_graph, "KeywordGraph")
