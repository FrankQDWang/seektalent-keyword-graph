from seektalent_keyword_graph.domain.normalization import normalize_surface


def test_normalize_full_width_k8s():
    assert normalize_surface("Ｋ８Ｓ") == "k8s"


def test_normalize_preserves_symbols():
    assert normalize_surface("C++") == "c++"
