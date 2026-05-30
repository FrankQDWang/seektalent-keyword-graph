from __future__ import annotations

from collections import Counter
from itertools import combinations


def count_cooccurrence(docs: list[dict]) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for doc in docs:
        surfaces = sorted(set(doc.get("surfaces", [])))
        for left, right in combinations(surfaces, 2):
            counts[(left, right)] += 1
    return counts
