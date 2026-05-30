from __future__ import annotations


def build_sampling_rows(items: list[dict]) -> list[dict]:
    return [
        {
            "surface": item["surface"],
            "risk": item["risk"],
            "decision": "pending",
        }
        for item in items
    ]
