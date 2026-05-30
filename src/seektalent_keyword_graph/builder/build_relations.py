from __future__ import annotations


def build_seed_relations(surfaces: list[str]) -> list[dict]:
    normalized = {surface.casefold() for surface in surfaces}
    relations: list[dict] = []
    if "k8s" in normalized and "kubernetes" in normalized:
        relations.append(
            {
                "from_surface": "k8s",
                "to_surface": "kubernetes",
                "relation_type": "abbreviates",
            }
        )
    return relations
