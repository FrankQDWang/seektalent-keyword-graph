from __future__ import annotations


def summarize_replay(results: list[dict]) -> dict:
    warning_count = sum(len(result.get("warnings", [])) for result in results)
    return {"case_count": len(results), "warning_count": warning_count}
