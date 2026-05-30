from __future__ import annotations


class FakeCtsCountClient:
    def __init__(self, totals: dict[str, int | str]) -> None:
        self.totals = totals

    def search_count(self, query_text: str) -> dict:
        value = self.totals.get(query_text, 0)
        if value == "timeout":
            raise TimeoutError(query_text)
        if value == "rate_limited":
            return {"query_text": query_text, "total": None, "status": "rate_limited"}
        if value == "api_error":
            return {"query_text": query_text, "total": None, "status": "api_error"}
        if value == "auth_error":
            return {"query_text": query_text, "total": None, "status": "auth_error"}
        return {"query_text": query_text, "total": int(value), "status": "success"}
