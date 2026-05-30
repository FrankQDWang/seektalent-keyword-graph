from __future__ import annotations


class CtsCountClient:
    def __init__(self, base_url: str, tenant_key: str, tenant_secret: str) -> None:
        self.base_url = base_url
        self.tenant_key = tenant_key
        self.tenant_secret = tenant_secret

    def __repr__(self) -> str:
        return f"CtsCountClient(base_url={self.base_url!r}, tenant_key={self.tenant_key!r})"

    def build_payload(self, keyword: str) -> dict:
        return {"keyword": keyword, "page": 1, "pageSize": 1}

    def parse_response(self, keyword: str, payload: dict) -> dict:
        total = int(payload["data"]["total"])
        return {"query_text": keyword, "total": total, "status": "success"}
