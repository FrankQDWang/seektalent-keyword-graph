from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from seektalent_keyword_graph import cli
from seektalent_keyword_graph.inspector.server import (
    InspectorServerConfig,
    create_server,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def fixture_flow_result(tmp_path_factory: pytest.TempPathFactory) -> Any:
    loader_path = ROOT / "tests" / "integration" / "_fixture_flow_loader.py"
    spec = importlib.util.spec_from_file_location(
        "inspector_fixture_loader", loader_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_run_fixture_flow()(
        tmp_path_factory.mktemp("inspector-startup")
    )


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


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return response.read().decode("utf-8")


def test_inspect_ui_help_is_on_existing_keyword_graph_script(capsys) -> None:
    code = cli.main(["inspect-ui", "--help"])
    captured = capsys.readouterr()

    assert code == 0, captured.err
    assert "usage: keyword-graph inspect-ui" in captured.out
    assert "--snapshot" in captured.out
    assert "--manifest" in captured.out
    assert "--port" in captured.out


def test_server_rejects_invalid_startup_arguments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="manifest override requires --snapshot"):
        InspectorServerConfig(manifest_path=tmp_path / "snapshot-manifest.json")

    with pytest.raises(ValueError, match="port must be between 0 and 65535"):
        InspectorServerConfig(port=70000)


def test_server_starts_against_bundled_snapshot_by_default() -> None:
    with running_server(InspectorServerConfig(port=0)) as base_url:
        providers = get_json(f"{base_url}/api/providers")
        meta = get_json(f"{base_url}/api/meta")

    assert providers == {"providers": ["boss", "cts", "liepin"], "default": "cts"}
    assert meta["snapshot"]["source"] == "bundled"
    assert meta["snapshot"]["path"].endswith("keyword-graph.sqlite3")
    assert meta["snapshot"]["manifest_path"].endswith("snapshot-manifest.json")
    assert meta["meta"]["kg_snapshot_id"] == "kg-eval-fixture"
    assert meta["meta"]["selection_policy_version"] == "policy-v1"


def test_server_starts_with_snapshot_and_manifest_override(
    fixture_flow_result: Any,
) -> None:
    config = InspectorServerConfig(
        port=0,
        snapshot_path=fixture_flow_result.snapshot_path,
        manifest_path=fixture_flow_result.manifest_path,
    )

    with running_server(config) as base_url:
        meta = get_json(f"{base_url}/api/meta")

    assert meta["snapshot"] == {
        "source": "override",
        "path": str(fixture_flow_result.snapshot_path),
        "manifest_path": str(fixture_flow_result.manifest_path),
    }
    assert meta["providers"] == ["boss", "cts", "liepin"]
    assert meta["meta"]["kg_snapshot_id"] == "kg-eval-fixture"


def test_static_inspector_assets_are_served_from_package_data() -> None:
    with running_server(InspectorServerConfig(port=0)) as base_url:
        index = get_text(f"{base_url}/")
        css = get_text(f"{base_url}/assets/app.css")
        js = get_text(f"{base_url}/assets/app.js")

    assert '<main class="inspector-shell">' in index
    assert 'id="query-text"' in index
    assert "Local Snapshot Inspector" in index
    assert ".inspector-shell" in css
    assert "submitQueryRecall" in js
