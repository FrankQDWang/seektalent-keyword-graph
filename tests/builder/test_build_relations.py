from seektalent_keyword_graph.builder.build_relations import build_seed_relations


def test_k8s_aliases_kubernetes():
    relations = build_seed_relations(["k8s", "Kubernetes"])

    assert {
        "from_surface": "k8s",
        "to_surface": "kubernetes",
        "relation_type": "abbreviates",
    } in relations


def test_vue_and_react_do_not_merge():
    relations = build_seed_relations(["Vue", "React"])

    assert relations == []
