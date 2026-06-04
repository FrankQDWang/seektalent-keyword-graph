from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from seektalent_keyword_graph.inspector.server import (
    InspectorServerConfig,
    create_server,
)

ROOT = Path(__file__).resolve().parents[2]


class InspectorDomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.forms: list[str] = []
        self.tables = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attr_map = dict(attrs)
        element_id = attr_map.get("id")
        if element_id is not None:
            self.ids.add(element_id)
        if tag == "form":
            form_id = attr_map.get("id")
            if form_id is not None:
                self.forms.append(form_id)
        if tag == "table":
            self.tables += 1


@pytest.fixture(scope="module")
def fixture_flow_result(tmp_path_factory: pytest.TempPathFactory) -> Any:
    loader_path = ROOT / "tests" / "integration" / "_fixture_flow_loader.py"
    spec = importlib.util.spec_from_file_location("inspector_dom_fixture", loader_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_run_fixture_flow()(tmp_path_factory.mktemp("inspector-dom"))


@contextmanager
def running_server(config: InspectorServerConfig) -> Iterator[str]:
    server = create_server(config)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict[str, object]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_http_dom_smoke_covers_react_and_empty_state(fixture_flow_result: Any) -> None:
    config = InspectorServerConfig(
        port=0,
        snapshot_path=fixture_flow_result.snapshot_path,
        manifest_path=fixture_flow_result.manifest_path,
    )
    with running_server(config) as base_url:
        html = get_text(f"{base_url}/")
        react_status, react_payload = post_json(
            f"{base_url}/api/query-recall",
            {"provider": "cts", "query_text": "React", "query_mode": "keyword"},
        )
        empty_status, empty_payload = post_json(
            f"{base_url}/api/query-recall",
            {"provider": "cts", "query_text": "GhostLang", "query_mode": "keyword"},
        )

    dom = InspectorDomParser()
    dom.feed(html)

    assert {"query-form", "query-text", "provider", "query-mode", "state"} <= dom.ids
    assert {"input-observation", "recommendations", "alternatives"} <= dom.ids
    assert dom.forms == ["query-form"]
    assert dom.tables == 1

    assert react_status == 200
    assert react_payload["response"]["input_observations"][0]["query_text"] == "React"
    assert react_payload["response"]["recommendations"][0]["action"] == (
        "add_alias_probe"
    )
    assert empty_status == 404
    assert empty_payload["error"]["code"] == "no_match"
    assert empty_payload["error"]["details"]["response"]["recommendations"][0][
        "action"
    ] == "fallback"
