from pathlib import Path

from seektalent_keyword_graph import KeywordGraph

FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")


def test_lookup_surface():
    graph = KeywordGraph.open(FIXTURE)
    surface = graph.lookup_surface("k8s")

    assert surface["display_text"] == "k8s"
    assert surface["latest_cts_total"] == 58692


def test_get_concept():
    graph = KeywordGraph.open(FIXTURE)
    concept = graph.get_concept("concept_kubernetes")

    assert concept["canonical_label"] == "Kubernetes"
