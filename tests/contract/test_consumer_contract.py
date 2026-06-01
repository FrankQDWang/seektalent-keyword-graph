from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryRecallRequest
from seektalent_keyword_graph.engine import KeywordGraph
from seektalent_keyword_graph.runtime.errors import SnapshotError

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
QUERY_PLAN_DIR = ROOT / "contracts" / "query-plan"
QUERY_RECALL_DIR = ROOT / "contracts" / "query-recall"


@pytest.fixture(scope="module")
def fixture_flow_result(tmp_path_factory: pytest.TempPathFactory) -> Any:
    return _load_run_fixture_flow()(tmp_path_factory.mktemp("consumer-contract"))


def test_runtime_settings_load_only_seektalent_keyword_graph_env() -> None:
    from seektalent_keyword_graph.config import KeywordGraphRuntimeSettings

    env = _GuardedEnv(
        {
            "SEEKTALENT_KEYWORD_GRAPH_ENABLED": "false",
            "SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH": "/srv/kg/snapshot.sqlite3",
            "SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID": "kg-eval-fixture",
            "SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN": "true",
            "SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES": "7",
            "SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER": "liepin",
            "SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES": "11",
            "KEYWORD_GRAPH_CTS_API_KEY": "must-not-be-read",
            "KEYWORD_GRAPH_CTS_BASE_URL": "must-not-be-read",
        }
    )

    settings = KeywordGraphRuntimeSettings.from_env(env)

    assert settings.enabled is False
    assert settings.snapshot_path == Path("/srv/kg/snapshot.sqlite3")
    assert settings.snapshot_id == "kg-eval-fixture"
    assert settings.fail_open is True
    assert settings.max_bundles == 7
    assert settings.default_provider == "liepin"
    assert settings.max_alternatives == 11
    assert env.keys_read == {
        "SEEKTALENT_KEYWORD_GRAPH_ENABLED",
        "SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH",
        "SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID",
        "SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN",
        "SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES",
        "SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER",
        "SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES",
    }


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("SEEKTALENT_KEYWORD_GRAPH_ENABLED", "maybe"),
        ("SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES", "many"),
    ],
)
def test_runtime_settings_parse_errors_name_env_var(
    env_name: str,
    env_value: str,
) -> None:
    from seektalent_keyword_graph.config import KeywordGraphRuntimeSettings

    env = _GuardedEnv(
        {
            env_name: env_value,
            "KEYWORD_GRAPH_CTS_API_KEY": "must-not-be-read",
        }
    )

    with pytest.raises(ValueError, match=env_name):
        KeywordGraphRuntimeSettings.from_env(env)


def test_sample_consumer_uses_public_runtime_facade_only(
    fixture_flow_result: Any,
) -> None:
    consumer = _SampleConsumer(
        fixture_flow_result.snapshot_path,
        fixture_flow_result.manifest_path,
        provider="cts",
    )

    plan = consumer.build_plan(
        [
            {"text": "Python 3", "strength": "required"},
            {"text": "Kubernetes", "strength": "required"},
            {"text": "React", "strength": "required"},
        ]
    )
    recall = consumer.analyze_recall(["React", "Kubernetes", "Kafka"])
    optimized = consumer.optimize_terms(["React", "Kubernetes", "Kafka"])

    assert plan.kg_snapshot_id == "kg-eval-fixture"
    assert {bundle.bundle_type for bundle in plan.query_bundles} >= {
        "anchor",
        "precision",
        "alias_probe",
    }
    assert recall.provider == "cts"
    assert recall.input_observations
    assert [term.action for term in optimized.optimized_terms][:3] == [
        "replace",
        "keep",
        "add_precision_companion",
    ]


def test_fail_open_adapter_represents_missing_graph_as_unavailable(
    tmp_path: Path,
) -> None:
    missing_snapshot = tmp_path / "missing.sqlite3"

    missing_snapshot_result = _documented_fail_open_adapter(missing_snapshot)
    missing_package_result = _documented_fail_open_adapter(
        missing_snapshot,
        import_keyword_graph=lambda: (_ for _ in ()).throw(ImportError("missing")),
    )
    import_os_error_result = _documented_fail_open_adapter(
        missing_snapshot,
        import_keyword_graph=lambda: (_ for _ in ()).throw(OSError("blocked")),
    )

    assert missing_snapshot_result == {
        "status": "keyword_graph_unavailable",
        "reason": "SnapshotFormatError",
    }
    assert missing_package_result == {
        "status": "keyword_graph_unavailable",
        "reason": "ImportError",
    }
    assert import_os_error_result == {
        "status": "keyword_graph_unavailable",
        "reason": "OSError",
    }

    docs = (DOCS_DIR / "seektalent-integration.md").read_text(encoding="utf-8")
    fail_open_example = docs.split("## Fail Open", maxsplit=1)[1].split(
        "```", maxsplit=2
    )[1]
    assert "keyword_graph_unavailable" in docs
    assert "try:\n        from seektalent_keyword_graph import KeywordGraph" in (
        fail_open_example
    )
    assert "ImportError`, `OSError`, and\n`SnapshotError" in docs


def test_contract_examples_are_fixture_derived_and_provider_aware() -> None:
    plan_request = json.loads(
        (QUERY_PLAN_DIR / "request.example.json").read_text(encoding="utf-8")
    )
    plan_response = json.loads(
        (QUERY_PLAN_DIR / "response.example.json").read_text(encoding="utf-8")
    )
    recall_request = json.loads(
        (QUERY_RECALL_DIR / "request.example.json").read_text(encoding="utf-8")
    )
    recall_response = json.loads(
        (QUERY_RECALL_DIR / "response.example.json").read_text(encoding="utf-8")
    )

    assert plan_request["request_id"] == "plan-full-bundle-matrix"
    assert plan_response["kg_snapshot_id"] == "kg-eval-fixture"
    assert {bundle["bundle_type"] for bundle in plan_response["query_bundles"]} == {
        "anchor",
        "precision",
        "alias_probe",
        "exploration",
    }
    assert {
        rejection["reason_code"] for rejection in plan_response["rejected_surfaces"]
    } >= {"company_like", "department_like"}
    assert "snapshot:kg-eval-fixture" in plan_response["lineage"]["source_refs"]

    assert recall_request["request_id"] == "recall-cts-term-pool"
    assert recall_request["provider"] == "cts"
    assert all(
        term["source"] == "query_term_pool"
        for term in recall_request["query_terms"]
    )
    assert recall_response["kg_snapshot_id"] == "kg-eval-fixture"
    assert recall_response["input_observations"]
    assert {
        observation["provider"] for observation in recall_response["input_observations"]
    } == {"cts"}
    assert {"boss", "cts", "liepin"} <= set(
        recall_response["lineage"]["provider_sources"]
    )
    assert "snapshot:kg-eval-fixture" in recall_response["lineage"]["source_refs"]
    assert {term["action"] for term in recall_response["optimized_terms"]} >= {
        "replace",
        "keep",
        "add_precision_companion",
        "score_only",
        "fallback",
    }
    recommendation_actions = {
        recommendation["action"]
        for recommendation in recall_response["recommendations"]
    }
    assert recommendation_actions >= {
        "replace",
        "add_precision_companion",
        "score_only",
        "fallback",
    }


def test_docs_define_consumer_env_and_query_recall_position() -> None:
    integration = (DOCS_DIR / "seektalent-integration.md").read_text(encoding="utf-8")
    recall_doc = (DOCS_DIR / "query-recall-optimization.md").read_text(encoding="utf-8")
    query_plan_doc = (DOCS_DIR / "query-plan-contract.md").read_text(encoding="utf-8")

    assert "SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER" in integration
    assert "SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES" in integration
    assert "SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER" in recall_doc
    assert "SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES" in recall_doc
    assert "no runtime network I/O" in integration
    assert "no CTS" in integration
    assert "compatibility rules" in query_plan_doc

    term_pool_index = recall_doc.index("SeekTalent query term pool generation")
    optimization_index = recall_doc.index("Query Recall Optimization")
    retrieval_index = recall_doc.index("provider retrieval")
    assert term_pool_index < optimization_index < retrieval_index
    assert "Do not modify the SeekTalent main project" in integration
    assert "Do not modify the SeekTalent main project" in recall_doc


def test_no_seektalent_module_import_exists() -> None:
    checked_roots = [
        ROOT / "src" / "seektalent_keyword_graph",
        ROOT / "tests",
        ROOT / "scripts",
    ]
    offending_imports: list[str] = []
    for root in checked_roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in {"SeekTalent", "seektalent"}:
                            offending_imports.append(f"{path}:{node.lineno}")
                elif (
                    isinstance(node, ast.ImportFrom)
                    and node.module in {"SeekTalent", "seektalent"}
                ):
                    offending_imports.append(f"{path}:{node.lineno}")

    assert offending_imports == []


class _GuardedEnv(dict[str, str]):
    def __init__(self, values: dict[str, str]) -> None:
        super().__init__(values)
        self.keys_read: set[str] = set()

    def get(self, key: str, default: Any = None) -> Any:
        if key.startswith("KEYWORD_GRAPH_CTS_"):
            raise AssertionError(f"runtime config read forbidden CTS env var {key}")
        self.keys_read.add(key)
        return super().get(key, default)

    def __iter__(self) -> Any:
        raise AssertionError("runtime config must not scan all environment variables")

    def items(self) -> Any:
        raise AssertionError("runtime config must not scan all environment variables")


class _SampleConsumer:
    def __init__(
        self,
        snapshot_path: Path,
        manifest_path: Path,
        *,
        provider: str,
    ) -> None:
        self.snapshot_path = snapshot_path
        self.manifest_path = manifest_path
        self.provider = provider

    def build_plan(self, terms: list[dict[str, str]]) -> Any:
        graph = KeywordGraph.open(self.snapshot_path, self.manifest_path)
        try:
            return graph.build_query_plan(
                QueryPlanRequest(
                    request_id="consumer-plan",
                    requirement_terms=terms,
                    max_query_bundles=10,
                )
            )
        finally:
            graph.close()

    def analyze_recall(self, terms: list[str]) -> Any:
        graph = KeywordGraph.open(self.snapshot_path, self.manifest_path)
        try:
            return graph.analyze_query_recall(
                QueryRecallRequest(
                    request_id="consumer-recall",
                    provider=self.provider,
                    query_terms=[{"text": term} for term in terms],
                    max_alternatives=10,
                )
            )
        finally:
            graph.close()

    def optimize_terms(self, terms: list[str]) -> Any:
        graph = KeywordGraph.open(self.snapshot_path, self.manifest_path)
        try:
            return graph.optimize_query_terms(
                QueryRecallRequest(
                    request_id="consumer-optimize",
                    provider=self.provider,
                    query_terms=[{"text": term} for term in terms],
                    max_alternatives=10,
                )
            )
        finally:
            graph.close()


def _documented_fail_open_adapter(
    snapshot_path: Path,
    manifest_path: Path | None = None,
    *,
    import_keyword_graph: Any = lambda: KeywordGraph,
) -> dict[str, str]:
    unavailable_errors = (ImportError, OSError, SnapshotError)
    try:
        graph_cls = import_keyword_graph()
        graph_cls.open(snapshot_path, manifest_path)
    except ImportError as exc:
        return {
            "status": "keyword_graph_unavailable",
            "reason": type(exc).__name__,
        }
    except unavailable_errors as exc:
        return {
            "status": "keyword_graph_unavailable",
            "reason": type(exc).__name__,
        }
    raise AssertionError("expected missing graph to fail open")


def _load_run_fixture_flow() -> Any:
    script_path = ROOT / "scripts" / "run_fixture_flow.py"
    spec = importlib.util.spec_from_file_location("run_fixture_flow", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load fixture flow script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.run_fixture_flow
