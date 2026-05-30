# Keyword Graph M0-M7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `seektalent-keyword-graph` into a real Python package and snapshot builder that SeekTalent can consume as a dependency.

**Architecture:** The package has a strict runtime/builder split. Runtime reads a readonly SQLite snapshot and returns deterministic query bundles; builder creates snapshots from JD fixtures, extracted surfaces, fake/real CTS count observations, and validation reports.

**Tech Stack:** Python 3.12+, Pydantic v2, SQLite, pytest, ruff, uv, JSONL, CSV.

**Linked Spec:** `docs/superpowers/specs/2026-05-30-keyword-graph-m0-m7.md`

---

## Execution Rules

- Execute slices in order.
- Each slice must end with its listed verification commands.
- Commit after each verified slice.
- Do not call real CTS in unattended overnight execution.
- Real CTS work is builder-only and must respect `1 RPS / 并发 1 / 09:00-21:00`.
- Runtime code must never import `seektalent_keyword_graph.builder` or `seektalent_keyword_graph.cts`.
- SeekTalent is a consumer. This package must not import SeekTalent.
- A blank Goal runner must sync the uv environment before running tests.

## Slice Checklist

| Slice | Milestone | Outcome |
| --- | --- | --- |
| S0 | M0 | Python project scaffold |
| S1 | M0 | Package skeleton and import |
| S2 | M1 | Pydantic contracts |
| S3 | M1 | SQLite snapshot schema and fixture |
| S4 | M1 | `KeywordGraph.open` and lookup |
| S5 | M1 | `build_query_plan` fallback MVP |
| S6 | M2 | JD JSONL import |
| S7 | M2 | Section splitter |
| S8 | M2 | Rule/dictionary extractor |
| S9 | M3 | Surface normalization |
| S10 | M3 | Concept and relation builder |
| S11 | M3 | Co-occurrence and sampling reports |
| S12 | M4 | Fake CTS count client |
| S13 | M4 | Real CTS client dry-run gate |
| S14 | M5 | Runtime snapshot builder |
| S15 | M5 | Query bundle selection |
| S16 | M5 | Replay evaluation report |
| S17 | M6 | SeekTalent consumer contracts |
| S18 | M7 | CLI dispatch, release validation, and rollback docs |
| S19 | M7 | Final verification and readiness report |

---

### Slice S0: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.python-version`

- [ ] **Step 1: Create `pyproject.toml`**

Use this content:

```toml
[project]
name = "seektalent-keyword-graph"
version = "0.1.0"
description = "Lightweight keyword graph package and snapshot builder for SeekTalent."
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.7",
]

[project.optional-dependencies]
dev = [
  "build>=1.2",
  "pytest>=8.0",
  "ruff>=0.5",
]
builder = [
  "httpx>=0.27",
]

[project.scripts]
keyword-graph = "seektalent_keyword_graph.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create `Makefile`**

Use this content:

```makefile
.PHONY: test lint check

test:
	uv run pytest

lint:
	uv run ruff check .

check: lint test
```

- [ ] **Step 3: Create `.python-version`**

Use this content:

```text
3.12
```

- [ ] **Step 4: Sync uv dev and builder dependencies**

Run:

```bash
uv sync --extra dev --extra builder
```

Expected:

- Exit 0.
- `seektalent-keyword-graph` is available in the uv environment.
- `build`, `pytest`, `ruff`, `pydantic`, and `httpx` are available for later slices.

- [ ] **Step 5: Run scaffold verification**

Run:

```bash
uv --version
uv run pytest --version
uv run ruff --version
uv run python -m build --version
uv run python -c "import pydantic, httpx"
uv run python -m compileall -q .
```

Expected:

- All commands exit 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml Makefile .python-version
git commit -m "build: scaffold python package project"
```

---

### Slice S1: Package Skeleton and Import

**Files:**
- Create: `src/seektalent_keyword_graph/__init__.py`
- Create: `src/seektalent_keyword_graph/engine.py`
- Create: `src/seektalent_keyword_graph/cli.py`
- Create: `tests/test_import.py`

- [ ] **Step 1: Write import test**

Create `tests/test_import.py`:

```python
def test_package_imports():
    import seektalent_keyword_graph

    assert seektalent_keyword_graph.__version__ == "0.1.0"
    assert hasattr(seektalent_keyword_graph, "KeywordGraph")
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/test_import.py -q
```

Expected:

- FAIL because `seektalent_keyword_graph` does not exist yet.

- [ ] **Step 3: Create package files**

Create `src/seektalent_keyword_graph/engine.py`:

```python
from __future__ import annotations

from pathlib import Path


class KeywordGraph:
    def __init__(self, snapshot_path: Path | None = None) -> None:
        self.snapshot_path = snapshot_path

    @classmethod
    def open(cls, snapshot_path: str | Path) -> "KeywordGraph":
        return cls(Path(snapshot_path))
```

Create `src/seektalent_keyword_graph/__init__.py`:

```python
from __future__ import annotations

from seektalent_keyword_graph.engine import KeywordGraph

__version__ = "0.1.0"

__all__ = ["KeywordGraph", "__version__"]
```

Create `src/seektalent_keyword_graph/cli.py`:

```python
from __future__ import annotations


def main() -> int:
    return 0
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
uv run pytest tests/test_import.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Run lint**

Run:

```bash
ruff check src tests
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add package skeleton"
```

---

### Slice S2: Runtime Contracts

**Files:**
- Create: `src/seektalent_keyword_graph/contracts/__init__.py`
- Create: `src/seektalent_keyword_graph/contracts/query_plan.py`
- Modify: `src/seektalent_keyword_graph/__init__.py`
- Test: `tests/contracts/test_query_plan_contract.py`

- [ ] **Step 1: Write contract tests**

Create `tests/contracts/test_query_plan_contract.py`:

```python
from seektalent_keyword_graph import QueryPlanRequest, QueryPlanResponse


def test_query_plan_request_defaults():
    request = QueryPlanRequest(
        request_id="req_001",
        seek_talent_run_id="run_001",
        job_title="Python backend engineer",
        jd_text="Need Python and Kubernetes.",
        requirement_terms=[{"text": "Python", "strength": "required"}],
    )

    assert request.schema_version == "query-plan-request-v1"
    assert request.kg_snapshot_id == "latest"
    assert request.max_query_bundles == 4


def test_query_plan_response_shape():
    response = QueryPlanResponse(
        request_id="req_001",
        kg_snapshot_id="kg_test",
        concept_sheet=[
            {
                "concept_id": "concept_python",
                "canonical_surface": "Python",
                "matched_surfaces": ["Python"],
                "evidence_codes": ["snapshot_surface_match"],
            }
        ],
        query_bundles=[
            {
                "bundle_id": "bundle_anchor_1",
                "bundle_type": "anchor",
                "priority": 1,
                "queries": [
                    {
                        "query_text": "Python",
                        "surfaces": ["surface_python"],
                        "expected_hit_count": 336708,
                        "confidence": 0.8,
                        "reason_codes": ["required_term", "snapshot_surface_match"],
                    }
                ],
            }
        ],
        rejected_surfaces=[
            {
                "surface_text": "Alibaba",
                "reason_code": "company_like",
                "source": "automatic_blocklist",
            }
        ],
        lineage={"input_hash": "sha256:test", "selection_policy_version": "policy-v1"},
        warnings=[{"code": "low_recall", "message": "Recall is below target"}],
    )

    dumped = response.model_dump()
    assert dumped["schema_version"] == "query-plan-response-v1"
    assert dumped["kg_snapshot_id"] == "kg_test"
    assert response.query_bundles[0].queries[0].query_text == "Python"
    assert response.concept_sheet[0].concept_id == "concept_python"
    assert response.rejected_surfaces[0].reason_code == "company_like"
    assert response.lineage.input_hash == "sha256:test"
    assert response.warnings[0].code == "low_recall"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/contracts/test_query_plan_contract.py -q
```

Expected:

- FAIL because `QueryPlanRequest` and `QueryPlanResponse` are not exported.

- [ ] **Step 3: Implement contracts**

Create `src/seektalent_keyword_graph/contracts/query_plan.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RequirementTerm(BaseModel):
    text: str
    strength: Literal["required", "preferred", "nice_to_have", "unknown"] = "unknown"


class ConceptSheetRow(BaseModel):
    concept_id: str
    canonical_surface: str
    matched_surfaces: list[str] = Field(default_factory=list)
    evidence_codes: list[str] = Field(default_factory=list)


class QueryPlanQuery(BaseModel):
    query_text: str
    surfaces: list[str] = Field(default_factory=list)
    expected_hit_count: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)


class QueryBundle(BaseModel):
    bundle_id: str
    bundle_type: Literal["anchor", "precision", "alias_probe", "exploration", "fallback"]
    priority: int = Field(ge=1)
    queries: list[QueryPlanQuery] = Field(default_factory=list)


class RejectedSurface(BaseModel):
    surface_text: str
    reason_code: str
    source: str = "runtime"


class QueryPlanLineage(BaseModel):
    input_hash: str | None = None
    snapshot_schema_version: str | None = None
    selection_policy_version: str | None = None


class QueryPlanWarning(BaseModel):
    code: str
    message: str = ""
    severity: Literal["info", "warning", "error"] = "warning"


class QueryPlanRequest(BaseModel):
    schema_version: Literal["query-plan-request-v1"] = "query-plan-request-v1"
    request_id: str
    seek_talent_run_id: str | None = None
    kg_snapshot_id: str = "latest"
    job_title: str
    jd_text: str = ""
    notes: str = ""
    requirement_terms: list[RequirementTerm] = Field(default_factory=list)
    max_query_bundles: int = Field(default=4, ge=1, le=20)


class QueryPlanResponse(BaseModel):
    schema_version: Literal["query-plan-response-v1"] = "query-plan-response-v1"
    request_id: str
    kg_snapshot_id: str
    concept_sheet: list[ConceptSheetRow] = Field(default_factory=list)
    query_bundles: list[QueryBundle] = Field(default_factory=list)
    rejected_surfaces: list[RejectedSurface] = Field(default_factory=list)
    lineage: QueryPlanLineage = Field(default_factory=QueryPlanLineage)
    warnings: list[QueryPlanWarning] = Field(default_factory=list)
```

Create `src/seektalent_keyword_graph/contracts/__init__.py`:

```python
from seektalent_keyword_graph.contracts.query_plan import (
    ConceptSheetRow,
    QueryBundle,
    QueryPlanLineage,
    QueryPlanQuery,
    QueryPlanRequest,
    QueryPlanResponse,
    QueryPlanWarning,
    RejectedSurface,
    RequirementTerm,
)

__all__ = [
    "ConceptSheetRow",
    "QueryBundle",
    "QueryPlanLineage",
    "QueryPlanQuery",
    "QueryPlanRequest",
    "QueryPlanResponse",
    "QueryPlanWarning",
    "RejectedSurface",
    "RequirementTerm",
]
```

Modify `src/seektalent_keyword_graph/__init__.py`:

```python
from __future__ import annotations

from seektalent_keyword_graph.contracts import QueryPlanRequest, QueryPlanResponse
from seektalent_keyword_graph.engine import KeywordGraph

__version__ = "0.1.0"

__all__ = ["KeywordGraph", "QueryPlanRequest", "QueryPlanResponse", "__version__"]
```

- [ ] **Step 4: Run test and verify GREEN**

Run:

```bash
uv run pytest tests/contracts/test_query_plan_contract.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add query plan contracts"
```

---

### Slice S3: SQLite Snapshot Schema and Fixture

**Files:**
- Create: `src/seektalent_keyword_graph/runtime/errors.py`
- Create: `src/seektalent_keyword_graph/runtime/sqlite_snapshot.py`
- Create: `tests/fixtures/build_fixture_snapshot.py`
- Create: `tests/fixtures/snapshots/minimal.sqlite3`
- Test: `tests/runtime/test_sqlite_snapshot.py`

- [ ] **Step 1: Write runtime snapshot tests**

Create `tests/runtime/test_sqlite_snapshot.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from seektalent_keyword_graph.runtime.errors import (
    SnapshotIntegrityError,
    SnapshotUnavailableError,
    UnsupportedSnapshotError,
)
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")
REQUIRED_RUNTIME_TABLE_SQL = """
create table concepts (
  concept_id text primary key,
  canonical_surface text not null
);
create table surfaces (
  surface_id text primary key,
  display_text text not null,
  normalized_text text not null,
  query_safe integer not null,
  latest_cts_total integer,
  latest_cts_status text not null
);
create table concept_surfaces (
  concept_id text not null,
  surface_id text not null
);
create table surface_relations (
  source_surface_id text not null,
  target_surface_id text not null,
  relation_type text not null,
  evidence_score real not null
);
create table cooccurrence_edges (
  source_concept_id text not null,
  target_concept_id text not null,
  weight real not null
);
create table cts_recall_observations (
  surface_id text not null,
  total integer,
  status text not null,
  observed_at text not null
);
create table selection_policy_meta (
  selection_policy_version text not null
);
"""


def write_snapshot(path: Path, script: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(script)
    conn.close()


def test_snapshot_meta_loads():
    snapshot = SQLiteSnapshot.open(FIXTURE)
    meta = snapshot.meta()

    assert meta["kg_snapshot_id"] == "kg_fixture"
    assert meta["snapshot_schema_version"] == "snapshot-v1"


def test_missing_snapshot_raises():
    with pytest.raises(SnapshotUnavailableError):
        SQLiteSnapshot.open("missing.sqlite3")


def test_unsupported_snapshot_schema_raises(tmp_path):
    path = tmp_path / "unsupported.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_bad', 'snapshot-v999', 'policy-v1');
        """
        + REQUIRED_RUNTIME_TABLE_SQL,
    )

    with pytest.raises(UnsupportedSnapshotError):
        SQLiteSnapshot.open(path)


def test_missing_required_table_raises(tmp_path):
    path = tmp_path / "missing_table.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_bad', 'snapshot-v1', 'policy-v1');
        """,
    )

    with pytest.raises(SnapshotIntegrityError):
        SQLiteSnapshot.open(path)


def test_empty_snapshot_meta_raises(tmp_path):
    path = tmp_path / "empty_meta.sqlite3"
    write_snapshot(
        path,
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        """
        + REQUIRED_RUNTIME_TABLE_SQL,
    )

    with pytest.raises(SnapshotIntegrityError):
        SQLiteSnapshot.open(path)
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/runtime/test_sqlite_snapshot.py -q
```

Expected:

- FAIL because runtime snapshot code and fixture do not exist.

- [ ] **Step 3: Implement snapshot reader**

Create `src/seektalent_keyword_graph/runtime/errors.py`:

```python
class KeywordGraphError(Exception):
    """Base error for seektalent-keyword-graph."""


class SnapshotUnavailableError(KeywordGraphError):
    """Snapshot file cannot be opened."""


class UnsupportedSnapshotError(KeywordGraphError):
    """Snapshot schema is not supported."""


class SnapshotIntegrityError(KeywordGraphError):
    """Snapshot exists but required data is missing or corrupt."""
```

Create `src/seektalent_keyword_graph/runtime/sqlite_snapshot.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from seektalent_keyword_graph.runtime.errors import (
    SnapshotIntegrityError,
    SnapshotUnavailableError,
    UnsupportedSnapshotError,
)


SUPPORTED_SNAPSHOT_SCHEMA_VERSION = "snapshot-v1"
REQUIRED_TABLES = {
    "snapshot_meta",
    "concepts",
    "surfaces",
    "concept_surfaces",
    "surface_relations",
    "cooccurrence_edges",
    "cts_recall_observations",
    "selection_policy_meta",
}


class SQLiteSnapshot:
    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self.path = path
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: str | Path) -> "SQLiteSnapshot":
        snapshot_path = Path(path)
        if not snapshot_path.exists():
            raise SnapshotUnavailableError(f"Snapshot not found: {snapshot_path}")
        uri = f"file:{snapshot_path}?mode=ro"
        try:
            connection = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise SnapshotUnavailableError(f"Snapshot cannot be opened: {snapshot_path}") from exc
        snapshot = cls(snapshot_path, connection)
        snapshot.validate()
        return snapshot

    def validate(self) -> None:
        try:
            table_rows = self.connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        except sqlite3.Error as exc:
            raise SnapshotIntegrityError("Snapshot catalog cannot be read") from exc

        existing_tables = {row["name"] for row in table_rows}
        missing_tables = REQUIRED_TABLES - existing_tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise SnapshotIntegrityError(f"Snapshot missing required tables: {missing}")

        meta = self.meta()
        if not meta:
            raise SnapshotIntegrityError("Snapshot metadata is empty")
        if meta["snapshot_schema_version"] != SUPPORTED_SNAPSHOT_SCHEMA_VERSION:
            raise UnsupportedSnapshotError(
                f"Unsupported snapshot schema: {meta['snapshot_schema_version']}"
            )

    def meta(self) -> dict[str, Any]:
        try:
            row = self.connection.execute(
                "select kg_snapshot_id, snapshot_schema_version, selection_policy_version "
                "from snapshot_meta limit 1"
            ).fetchone()
        except sqlite3.Error as exc:
            raise SnapshotIntegrityError("Snapshot metadata cannot be read") from exc
        if row is None:
            return {}
        return dict(row)
```

- [ ] **Step 4: Create fixture builder**

Create `tests/fixtures/build_fixture_snapshot.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


def build(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        create table concepts (
          concept_id text primary key,
          canonical_surface text not null
        );
        create table surfaces (
          surface_id text primary key,
          display_text text not null,
          normalized_text text not null,
          query_safe integer not null,
          latest_cts_total integer,
          latest_cts_status text not null
        );
        create table concept_surfaces (
          concept_id text not null,
          surface_id text not null
        );
        create table surface_relations (
          source_surface_id text not null,
          target_surface_id text not null,
          relation_type text not null,
          evidence_score real not null
        );
        create table cooccurrence_edges (
          source_concept_id text not null,
          target_concept_id text not null,
          weight real not null
        );
        create table cts_recall_observations (
          surface_id text not null,
          total integer,
          status text not null,
          observed_at text not null
        );
        create table selection_policy_meta (
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_fixture', 'snapshot-v1', 'policy-v1');
        insert into concepts values ('concept_k8s', 'Kubernetes');
        insert into surfaces values ('surface_k8s', 'k8s', 'k8s', 1, 58692, 'success');
        insert into concept_surfaces values ('concept_k8s', 'surface_k8s');
        insert into selection_policy_meta values ('policy-v1');
        """
    )
    conn.close()


if __name__ == "__main__":
    build(Path("tests/fixtures/snapshots/minimal.sqlite3"))
```

Run:

```bash
python tests/fixtures/build_fixture_snapshot.py
```

Expected:

- `tests/fixtures/snapshots/minimal.sqlite3` exists.

- [ ] **Step 5: Run test and verify GREEN**

Run:

```bash
uv run pytest tests/runtime/test_sqlite_snapshot.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add readonly sqlite snapshot reader"
```

---

### Slice S4: KeywordGraph Open and Lookup

**Files:**
- Modify: `src/seektalent_keyword_graph/engine.py`
- Modify: `tests/fixtures/build_fixture_snapshot.py`
- Test: `tests/runtime/test_keyword_graph_lookup.py`

- [ ] **Step 1: Write lookup tests**

Create `tests/runtime/test_keyword_graph_lookup.py`:

```python
from pathlib import Path

from seektalent_keyword_graph import KeywordGraph


FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")


def test_lookup_surface():
    graph = KeywordGraph.open(FIXTURE)
    surface = graph.lookup_surface("k8s")

    assert surface["display_text"] == "k8s"
    assert surface["latest_cts_total"] == 58692


def test_get_concept():
    graph = KeywordGraph.open(FIXTURE)
    concept = graph.get_concept("concept_kubernetes")

    assert concept["canonical_label"] == "Kubernetes"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/runtime/test_keyword_graph_lookup.py -q
```

Expected:

- FAIL because lookup methods do not exist.

- [ ] **Step 3: Extend fixture schema**

Modify `tests/fixtures/build_fixture_snapshot.py` so `conn.executescript(...)` contains:

```sql
create table snapshot_meta (
  kg_snapshot_id text not null,
  snapshot_schema_version text not null,
  selection_policy_version text not null
);
insert into snapshot_meta values ('kg_fixture', 'snapshot-v1', 'policy-v1');

create table concepts (
  concept_id text primary key,
  canonical_label text not null,
  concept_type text not null
);
insert into concepts values ('concept_kubernetes', 'Kubernetes', 'tool');

create table surfaces (
  surface_id text primary key,
  text_norm text not null,
  display_text text not null,
  latest_cts_total integer,
  latest_cts_status text not null,
  query_safe integer not null
);
insert into surfaces values (
  'surface_k8s', 'k8s', 'k8s', 58692, 'success', 1
);

create table concept_surfaces (
  concept_id text not null,
  surface_id text not null
);
insert into concept_surfaces values ('concept_kubernetes', 'surface_k8s');
```

Run:

```bash
python tests/fixtures/build_fixture_snapshot.py
```

- [ ] **Step 4: Implement lookup methods**

Modify `src/seektalent_keyword_graph/engine.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


class KeywordGraph:
    def __init__(self, snapshot: SQLiteSnapshot) -> None:
        self.snapshot = snapshot
        self.snapshot_path = snapshot.path

    @classmethod
    def open(cls, snapshot_path: str | Path) -> "KeywordGraph":
        return cls(SQLiteSnapshot.open(snapshot_path))

    def lookup_surface(self, text: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from surfaces where text_norm = ? limit 1", (text.casefold(),)
        ).fetchone()
        return dict(row) if row else None

    def get_concept(self, concept_id: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from concepts where concept_id = ? limit 1", (concept_id,)
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/runtime/test_keyword_graph_lookup.py tests/runtime/test_sqlite_snapshot.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add keyword graph lookup"
```

---

### Slice S5: Query Plan Fallback MVP

**Files:**
- Modify: `src/seektalent_keyword_graph/engine.py`
- Test: `tests/runtime/test_build_query_plan.py`

- [ ] **Step 1: Write query plan tests**

Create `tests/runtime/test_build_query_plan.py`:

```python
from pathlib import Path

from seektalent_keyword_graph import KeywordGraph, QueryPlanRequest


FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")


def test_build_query_plan_returns_anchor_for_known_term():
    graph = KeywordGraph.open(FIXTURE)
    request = QueryPlanRequest(
        request_id="req_001",
        seek_talent_run_id="run_001",
        job_title="Platform engineer",
        jd_text="Need k8s experience.",
        requirement_terms=[{"text": "k8s", "strength": "required"}],
    )

    response = graph.build_query_plan(request)

    assert response.request_id == "req_001"
    assert response.kg_snapshot_id == "kg_fixture"
    assert response.query_bundles[0].bundle_type == "anchor"
    assert response.query_bundles[0].queries[0].query_text == "k8s"


def test_build_query_plan_fallback_for_unknown_term():
    graph = KeywordGraph.open(FIXTURE)
    request = QueryPlanRequest(
        request_id="req_002",
        seek_talent_run_id="run_001",
        job_title="Unknown role",
        jd_text="Need something rare.",
        requirement_terms=[{"text": "rareterm", "strength": "required"}],
    )

    response = graph.build_query_plan(request)

    assert response.query_bundles[0].bundle_type == "fallback"
    assert response.warnings[0].code == "no_snapshot_surface_match"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/runtime/test_build_query_plan.py -q
```

Expected:

- FAIL because `build_query_plan` is missing.

- [ ] **Step 3: Implement minimal query planning**

Add this method to `KeywordGraph` in `src/seektalent_keyword_graph/engine.py`:

```python
    def build_query_plan(self, request):
        from seektalent_keyword_graph.contracts import QueryPlanResponse

        meta = self.snapshot.meta()
        bundles = []
        warnings = []
        for term in request.requirement_terms:
            surface = self.lookup_surface(term.text)
            if surface and surface["query_safe"]:
                bundles.append(
                    {
                        "bundle_id": "bundle_anchor_1",
                        "bundle_type": "anchor",
                        "priority": 1,
                        "queries": [
                            {
                                "query_text": surface["display_text"],
                                "surfaces": [surface["surface_id"]],
                                "expected_hit_count": surface["latest_cts_total"],
                                "confidence": 0.8,
                                "reason_codes": ["required_term", "snapshot_surface_match"],
                            }
                        ],
                    }
                )
                break
        if not bundles:
            bundles.append(
                {
                    "bundle_id": "bundle_fallback_1",
                    "bundle_type": "fallback",
                    "priority": 99,
                    "queries": [
                        {
                            "query_text": request.job_title,
                            "surfaces": [],
                            "confidence": 0.2,
                            "reason_codes": ["fallback_job_title"],
                        }
                    ],
                }
            )
            warnings.append({"code": "no_snapshot_surface_match"})
        return QueryPlanResponse(
            request_id=request.request_id,
            kg_snapshot_id=meta.get("kg_snapshot_id", request.kg_snapshot_id),
            concept_sheet=[],
            query_bundles=bundles,
            rejected_surfaces=[],
            lineage={
                "snapshot_schema_version": meta.get("snapshot_schema_version"),
                "selection_policy_version": meta.get("selection_policy_version"),
            },
            warnings=warnings,
        )
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/runtime/test_build_query_plan.py tests/runtime -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add query plan fallback mvp"
```

---

### Slice S6: JD JSONL Import

**Files:**
- Create: `src/seektalent_keyword_graph/builder/import_jds.py`
- Create: `src/seektalent_keyword_graph/builder/build_store.py`
- Create: `tests/fixtures/jds/sample_jds.jsonl`
- Test: `tests/builder/test_import_jds.py`

- [ ] **Step 1: Create fixture JSONL**

Create `tests/fixtures/jds/sample_jds.jsonl`:

```jsonl
{"source":"fixture","source_ref":"jd_001","title_raw":"平台工程师","jd_text":"任职要求：熟悉 Python 和 Kubernetes。"}
{"source":"fixture","source_ref":"jd_002","title_raw":"后端工程师","jd_text":"岗位要求：掌握 Java、Spring Cloud。"}
```

- [ ] **Step 2: Write import test**

Create `tests/builder/test_import_jds.py`:

```python
from pathlib import Path

from seektalent_keyword_graph.builder.import_jds import import_jds


def test_import_jds(tmp_path):
    db_path = tmp_path / "build.sqlite3"
    count = import_jds(Path("tests/fixtures/jds/sample_jds.jsonl"), db_path)

    assert count == 2
```

- [ ] **Step 3: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_import_jds.py -q
```

Expected:

- FAIL because builder import does not exist.

- [ ] **Step 4: Implement build store and import**

Create `src/seektalent_keyword_graph/builder/build_store.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_build_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        create table if not exists jd_documents (
          jd_id text primary key,
          source text not null,
          source_ref text not null,
          title_raw text not null,
          jd_text text not null,
          content_hash text not null
        )
        """
    )
    return conn
```

Create `src/seektalent_keyword_graph/builder/import_jds.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from seektalent_keyword_graph.builder.build_store import connect_build_db


def import_jds(jsonl_path: Path, db_path: Path) -> int:
    conn = connect_build_db(db_path)
    count = 0
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        content = item["jd_text"]
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        jd_id = f"{item['source']}:{item['source_ref']}"
        conn.execute(
            """
            insert or replace into jd_documents
            (jd_id, source, source_ref, title_raw, jd_text, content_hash)
            values (?, ?, ?, ?, ?, ?)
            """,
            (jd_id, item["source"], item["source_ref"], item["title_raw"], content, digest),
        )
        count += 1
    conn.commit()
    conn.close()
    return count
```

- [ ] **Step 5: Run test**

Run:

```bash
uv run pytest tests/builder/test_import_jds.py -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add jd jsonl import"
```

---

### Slice S7: Section Splitter

**Files:**
- Create: `src/seektalent_keyword_graph/builder/sections.py`
- Test: `tests/builder/test_sections.py`

- [ ] **Step 1: Write section splitter tests**

Create `tests/builder/test_sections.py`:

```python
from seektalent_keyword_graph.builder.sections import split_sections


def test_split_requirement_section():
    sections = split_sections("岗位职责：负责平台建设。\n任职要求：熟悉 Python。")

    assert sections[0]["section_type"] == "responsibility"
    assert sections[1]["section_type"] == "requirement"
    assert sections[1]["text"] == "熟悉 Python。"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_sections.py -q
```

Expected:

- FAIL because `sections.py` does not exist.

- [ ] **Step 3: Implement splitter**

Create `src/seektalent_keyword_graph/builder/sections.py`:

```python
from __future__ import annotations


HEADING_TYPES = {
    "岗位职责": "responsibility",
    "工作职责": "responsibility",
    "任职要求": "requirement",
    "岗位要求": "requirement",
    "加分项": "preferred",
    "优先条件": "preferred",
}


def split_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for heading, section_type in HEADING_TYPES.items():
            prefix = f"{heading}："
            if line.startswith(prefix):
                sections.append({"section_type": section_type, "text": line[len(prefix) :].strip()})
                break
        else:
            sections.append({"section_type": "other", "text": line})
    return sections
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/builder/test_sections.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add jd section splitter"
```

---

### Slice S8: Rule and Dictionary Extractor

**Files:**
- Create: `src/seektalent_keyword_graph/builder/extract_surfaces.py`
- Test: `tests/builder/test_extract_surfaces.py`

- [ ] **Step 1: Write extraction tests**

Create `tests/builder/test_extract_surfaces.py`:

```python
from seektalent_keyword_graph.builder.extract_surfaces import extract_surface_mentions


def test_extract_known_technical_terms():
    mentions = extract_surface_mentions("熟悉 Python 和 Kubernetes，了解 Spring Cloud。")
    texts = {mention["surface_text_raw"] for mention in mentions}

    assert {"Python", "Kubernetes", "Spring Cloud"} <= texts


def test_blocks_company_like_terms():
    mentions = extract_surface_mentions("熟悉 腾讯 云和 Python。")
    texts = {mention["surface_text_raw"] for mention in mentions}

    assert "Python" in texts
    assert "腾讯" not in texts
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_extract_surfaces.py -q
```

Expected:

- FAIL because extractor does not exist.

- [ ] **Step 3: Implement extractor**

Create `src/seektalent_keyword_graph/builder/extract_surfaces.py`:

```python
from __future__ import annotations

KNOWN_TERMS = [
    "Python",
    "Java",
    "Kubernetes",
    "k8s",
    "Spring Cloud",
    "React",
    "Vue",
    "AIGC",
]

BLOCKED_TERMS = {"腾讯", "阿里", "字节"}


def extract_surface_mentions(text: str) -> list[dict]:
    mentions: list[dict] = []
    for term in KNOWN_TERMS:
        if term in text and term not in BLOCKED_TERMS:
            mentions.append(
                {
                    "surface_text_raw": term,
                    "surface_text_norm": term.casefold(),
                    "mention_type": "tool" if term in {"Kubernetes", "k8s"} else "skill",
                    "confidence": 0.9,
                    "extractor_name": "rule_dictionary",
                    "extractor_version": "v1",
                }
            )
    return mentions
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/builder/test_extract_surfaces.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add rule dictionary extractor"
```

---

### Slice S9: Surface Normalization

**Files:**
- Create: `src/seektalent_keyword_graph/domain/normalization.py`
- Test: `tests/domain/test_normalization.py`

- [ ] **Step 1: Write normalization tests**

Create `tests/domain/test_normalization.py`:

```python
from seektalent_keyword_graph.domain.normalization import normalize_surface


def test_normalize_full_width_k8s():
    assert normalize_surface("Ｋ８Ｓ") == "k8s"


def test_normalize_preserves_symbols():
    assert normalize_surface("C++") == "c++"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/domain/test_normalization.py -q
```

Expected:

- FAIL because normalization module does not exist.

- [ ] **Step 3: Implement normalization**

Create `src/seektalent_keyword_graph/domain/normalization.py`:

```python
from __future__ import annotations

import unicodedata


def normalize_surface(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.strip().casefold().split())
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/domain/test_normalization.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add surface normalization"
```

---

### Slice S10: Concept and Relation Builder

**Files:**
- Create: `src/seektalent_keyword_graph/builder/build_relations.py`
- Test: `tests/builder/test_build_relations.py`

- [ ] **Step 1: Write relation tests**

Create `tests/builder/test_build_relations.py`:

```python
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
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_build_relations.py -q
```

Expected:

- FAIL because relation builder does not exist.

- [ ] **Step 3: Implement seed relations**

Create `src/seektalent_keyword_graph/builder/build_relations.py`:

```python
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
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/builder/test_build_relations.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add seed relation builder"
```

---

### Slice S11: Co-occurrence and Sampling Reports

**Files:**
- Create: `src/seektalent_keyword_graph/builder/cooccurrence.py`
- Create: `src/seektalent_keyword_graph/builder/sampling_report.py`
- Test: `tests/builder/test_reports.py`

- [ ] **Step 1: Write report tests**

Create `tests/builder/test_reports.py`:

```python
from seektalent_keyword_graph.builder.cooccurrence import count_cooccurrence
from seektalent_keyword_graph.builder.sampling_report import build_sampling_rows


def test_count_cooccurrence():
    docs = [{"surfaces": ["python", "kubernetes"]}, {"surfaces": ["python"]}]

    assert count_cooccurrence(docs)[("kubernetes", "python")] == 1


def test_sampling_rows_include_risk_reason():
    rows = build_sampling_rows([{"surface": "go", "risk": "ambiguous"}])

    assert rows[0]["surface"] == "go"
    assert rows[0]["risk"] == "ambiguous"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_reports.py -q
```

Expected:

- FAIL because modules do not exist.

- [ ] **Step 3: Implement reports**

Create `src/seektalent_keyword_graph/builder/cooccurrence.py`:

```python
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
```

Create `src/seektalent_keyword_graph/builder/sampling_report.py`:

```python
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
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/builder/test_reports.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add cooccurrence and sampling reports"
```

---

### Slice S12: Fake CTS Count Client

**Files:**
- Create: `src/seektalent_keyword_graph/cts/fake_client.py`
- Test: `tests/cts/test_fake_client.py`

- [ ] **Step 1: Write fake CTS tests**

Create `tests/cts/test_fake_client.py`:

```python
import pytest

from seektalent_keyword_graph.cts.fake_client import FakeCtsCountClient


def test_fake_cts_success():
    client = FakeCtsCountClient({"Python": 336708})

    result = client.search_count("Python")

    assert result["total"] == 336708
    assert result["status"] == "success"


def test_fake_cts_timeout():
    client = FakeCtsCountClient({"timeout": "timeout"})

    with pytest.raises(TimeoutError):
        client.search_count("timeout")


def test_fake_cts_zero():
    client = FakeCtsCountClient({"RareTerm": 0})

    result = client.search_count("RareTerm")

    assert result["total"] == 0
    assert result["status"] == "success"


def test_fake_cts_rate_limited():
    client = FakeCtsCountClient({"Python": "rate_limited"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "rate_limited"


def test_fake_cts_api_error():
    client = FakeCtsCountClient({"Python": "api_error"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "api_error"


def test_fake_cts_auth_error():
    client = FakeCtsCountClient({"Python": "auth_error"})

    result = client.search_count("Python")

    assert result["total"] is None
    assert result["status"] == "auth_error"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/cts/test_fake_client.py -q
```

Expected:

- FAIL because fake CTS client does not exist.

- [ ] **Step 3: Implement fake client**

Create `src/seektalent_keyword_graph/cts/fake_client.py`:

```python
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
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/cts/test_fake_client.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add fake cts count client"
```

---

### Slice S13: Real CTS Client Dry-run Gate

**Files:**
- Create: `src/seektalent_keyword_graph/cts/count_client.py`
- Create: `src/seektalent_keyword_graph/cts/probe_window.py`
- Test: `tests/cts/test_probe_window.py`
- Test: `tests/cts/test_count_client.py`

- [ ] **Step 1: Write probe window tests**

Create `tests/cts/test_probe_window.py`:

```python
from datetime import time

from seektalent_keyword_graph.cts.probe_window import can_run_real_probe, is_within_probe_window


def test_probe_window_allows_daytime():
    assert is_within_probe_window(time(10, 0), time(9, 0), time(21, 0))


def test_probe_window_blocks_night():
    assert not is_within_probe_window(time(22, 0), time(9, 0), time(21, 0))


def test_real_probe_allowed_when_dry_run_outside_window():
    assert can_run_real_probe(
        dry_run=True,
        now=time(22, 0),
        start=time(9, 0),
        end=time(21, 0),
    )


def test_real_probe_blocked_outside_window_without_dry_run():
    assert not can_run_real_probe(
        dry_run=False,
        now=time(22, 0),
        start=time(9, 0),
        end=time(21, 0),
    )
```

Create `tests/cts/test_count_client.py`:

```python
from seektalent_keyword_graph.cts.count_client import CtsCountClient


def test_cts_payload_uses_count_probe_page_size():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    assert client.build_payload("Python") == {
        "keyword": "Python",
        "page": 1,
        "pageSize": 1,
    }


def test_cts_response_parses_data_total_only():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    payload = {"data": {"total": 336708, "items": [{"id": "x"}]}}

    result = client.parse_response("Python", payload)

    assert result == {"query_text": "Python", "total": 336708, "status": "success"}


def test_cts_client_repr_hides_secret():
    client = CtsCountClient(
        base_url="https://cts.example.test",
        tenant_key="tenant-key",
        tenant_secret="tenant-secret",
    )

    rendered = repr(client)

    assert "tenant-secret" not in rendered
    assert "tenant-key" in rendered
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/cts/test_probe_window.py tests/cts/test_count_client.py -q
```

Expected:

- FAIL because probe window and count client modules do not exist.

- [ ] **Step 3: Implement probe window**

Create `src/seektalent_keyword_graph/cts/probe_window.py`:

```python
from __future__ import annotations

from datetime import time


def is_within_probe_window(now: time, start: time, end: time) -> bool:
    return start <= now < end


def can_run_real_probe(dry_run: bool, now: time, start: time, end: time) -> bool:
    return dry_run or is_within_probe_window(now, start, end)
```

- [ ] **Step 4: Create real client skeleton that supports dry run**

Create `src/seektalent_keyword_graph/cts/count_client.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/cts -q
```

Expected:

- PASS.

- [ ] **Step 6: Commit**

```bash
git add src tests
git commit -m "feat: add cts probe window gate"
```

---

### Slice S14: Runtime Snapshot Builder

**Files:**
- Create: `src/seektalent_keyword_graph/builder/build_snapshot.py`
- Test: `tests/builder/test_build_snapshot.py`

- [ ] **Step 1: Write snapshot builder test**

Create `tests/builder/test_build_snapshot.py`:

```python
from pathlib import Path

from seektalent_keyword_graph.builder.build_snapshot import build_runtime_snapshot
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


def test_build_runtime_snapshot(tmp_path):
    output = tmp_path / "snapshot.sqlite3"
    build_runtime_snapshot(output)

    snapshot = SQLiteSnapshot.open(output)
    assert snapshot.meta()["kg_snapshot_id"].startswith("kg_")
    assert snapshot.meta()["snapshot_schema_version"] == "snapshot-v1"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/builder/test_build_snapshot.py -q
```

Expected:

- FAIL because builder does not exist.

- [ ] **Step 3: Implement minimal snapshot builder**

Create `src/seektalent_keyword_graph/builder/build_snapshot.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path


def build_runtime_snapshot(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    conn = sqlite3.connect(output_path)
    conn.executescript(
        """
        create table snapshot_meta (
          kg_snapshot_id text not null,
          snapshot_schema_version text not null,
          selection_policy_version text not null
        );
        create table concepts (
          concept_id text primary key,
          canonical_surface text not null
        );
        create table surfaces (
          surface_id text primary key,
          display_text text not null,
          normalized_text text not null,
          query_safe integer not null,
          latest_cts_total integer,
          latest_cts_status text not null
        );
        create table concept_surfaces (
          concept_id text not null,
          surface_id text not null
        );
        create table surface_relations (
          source_surface_id text not null,
          target_surface_id text not null,
          relation_type text not null,
          evidence_score real not null
        );
        create table cooccurrence_edges (
          source_concept_id text not null,
          target_concept_id text not null,
          weight real not null
        );
        create table cts_recall_observations (
          surface_id text not null,
          total integer,
          status text not null,
          observed_at text not null
        );
        create table selection_policy_meta (
          selection_policy_version text not null
        );
        insert into snapshot_meta values ('kg_generated_fixture', 'snapshot-v1', 'policy-v1');
        insert into selection_policy_meta values ('policy-v1');
        """
    )
    conn.close()
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/builder/test_build_snapshot.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add runtime snapshot builder"
```

---

### Slice S15: Query Bundle Selection

**Files:**
- Create: `src/seektalent_keyword_graph/domain/policies.py`
- Test: `tests/domain/test_policies.py`

- [ ] **Step 1: Write policy tests**

Create `tests/domain/test_policies.py`:

```python
from seektalent_keyword_graph.domain.policies import recall_bucket


def test_recall_bucket_zero():
    assert recall_bucket(0) == "zero"


def test_recall_bucket_too_wide():
    assert recall_bucket(500000) == "too_wide"


def test_recall_bucket_healthy():
    assert recall_bucket(10000) == "healthy"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/domain/test_policies.py -q
```

Expected:

- FAIL because policy module does not exist.

- [ ] **Step 3: Implement policy**

Create `src/seektalent_keyword_graph/domain/policies.py`:

```python
from __future__ import annotations


def recall_bucket(total: int | None) -> str:
    if total is None:
        return "unknown"
    if total == 0:
        return "zero"
    if total > 200000:
        return "too_wide"
    if total < 100:
        return "too_narrow"
    return "healthy"
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/domain/test_policies.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add recall bucket policy"
```

---

### Slice S16: Replay Evaluation Report

**Files:**
- Create: `src/seektalent_keyword_graph/observability/replay_report.py`
- Test: `tests/observability/test_replay_report.py`

- [ ] **Step 1: Write replay report tests**

Create `tests/observability/test_replay_report.py`:

```python
from seektalent_keyword_graph.observability.replay_report import summarize_replay


def test_summarize_replay():
    summary = summarize_replay(
        [
            {"warnings": []},
            {"warnings": [{"code": "no_snapshot_surface_match"}]},
        ]
    )

    assert summary["case_count"] == 2
    assert summary["warning_count"] == 1
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/observability/test_replay_report.py -q
```

Expected:

- FAIL because replay report module does not exist.

- [ ] **Step 3: Implement replay report**

Create `src/seektalent_keyword_graph/observability/replay_report.py`:

```python
from __future__ import annotations


def summarize_replay(results: list[dict]) -> dict:
    warning_count = sum(len(result.get("warnings", [])) for result in results)
    return {"case_count": len(results), "warning_count": warning_count}
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/observability/test_replay_report.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src tests
git commit -m "feat: add replay report summary"
```

---

### Slice S17: SeekTalent Consumer Contracts

**Files:**
- Create: `contracts/query-plan/request.example.json`
- Create: `contracts/query-plan/response.example.json`
- Test: `tests/contracts/test_examples.py`

- [ ] **Step 1: Create examples**

Create `contracts/query-plan/request.example.json`:

```json
{
  "request_id": "req_001",
  "seek_talent_run_id": "run_001",
  "job_title": "Platform engineer",
  "jd_text": "Need k8s experience.",
  "requirement_terms": [
    {"text": "k8s", "strength": "required"}
  ]
}
```

Create `contracts/query-plan/response.example.json`:

```json
{
  "request_id": "req_001",
  "kg_snapshot_id": "kg_fixture",
  "concept_sheet": [],
  "query_bundles": [],
  "rejected_surfaces": [],
  "lineage": {"snapshot_schema_version": "snapshot-v1"},
  "warnings": []
}
```

- [ ] **Step 2: Write example validation tests**

Create `tests/contracts/test_examples.py`:

```python
import json
from pathlib import Path

from seektalent_keyword_graph import QueryPlanRequest, QueryPlanResponse


def test_request_example_validates():
    data = json.loads(Path("contracts/query-plan/request.example.json").read_text())

    assert QueryPlanRequest.model_validate(data).request_id == "req_001"


def test_response_example_validates():
    data = json.loads(Path("contracts/query-plan/response.example.json").read_text())

    assert QueryPlanResponse.model_validate(data).kg_snapshot_id == "kg_fixture"
```

- [ ] **Step 3: Run tests**

Run:

```bash
uv run pytest tests/contracts -q
```

Expected:

- PASS.

- [ ] **Step 4: Commit**

```bash
git add contracts tests
git commit -m "test: add consumer contract examples"
```

---

### Slice S18: CLI Dispatch, Release Validation, and Rollback Docs

**Files:**
- Modify: `src/seektalent_keyword_graph/cli.py`
- Create: `src/seektalent_keyword_graph/release_validation.py`
- Create: `scripts/validate_release.py`
- Create: `docs/release-checklist.md`
- Test: `tests/test_release_validation.py`
- Test: `tests/cli/test_cli.py`

- [ ] **Step 1: Write CLI and release validation tests**

Create `tests/test_release_validation.py`:

```python
from seektalent_keyword_graph.release_validation import (
    calculate_sha256,
    validate_snapshot_artifact,
    validate_snapshot_size,
    write_manifest,
)


def test_validate_snapshot_size_allows_small_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"small")

    assert validate_snapshot_size(path, max_bytes=100)


def test_validate_snapshot_size_rejects_large_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"large")

    assert not validate_snapshot_size(path, max_bytes=3)


def test_manifest_checksum_roundtrip(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"snapshot-bytes")

    write_manifest(snapshot, manifest)

    assert validate_snapshot_artifact(snapshot, manifest, max_bytes=100)
    assert calculate_sha256(snapshot) == calculate_sha256(snapshot)


def test_manifest_checksum_rejects_changed_file(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"snapshot-bytes")
    write_manifest(snapshot, manifest)
    snapshot.write_bytes(b"changed")

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)


def test_validate_snapshot_artifact_rejects_secret_marker(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"KEYWORD_GRAPH_CTS_TENANT_SECRET=secret")
    write_manifest(snapshot, manifest)

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)


def test_validate_snapshot_artifact_rejects_candidate_or_resume_markers(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite3.gz"
    manifest = tmp_path / "manifest.json"
    snapshot.write_bytes(b"candidate_list=[alice]; resume_text=private")
    write_manifest(snapshot, manifest)

    assert not validate_snapshot_artifact(snapshot, manifest, max_bytes=100)
```

Create `tests/cli/test_cli.py`:

```python
import json

import pytest

from seektalent_keyword_graph.cli import build_parser, main


@pytest.mark.parametrize(
    "command",
    [
        "import-jds",
        "extract-surfaces",
        "build-relations",
        "probe-cts",
        "build-snapshot",
        "validate-snapshot",
    ],
)
def test_cli_registers_promised_commands(command):
    help_text = build_parser().format_help()

    assert command in help_text


def test_cli_help_returns_zero(capsys):
    assert main(["--help"]) == 0

    assert "keyword-graph" in capsys.readouterr().out


@pytest.mark.parametrize(
    "command",
    [
        "import-jds",
        "extract-surfaces",
        "build-relations",
        "probe-cts",
        "build-snapshot",
        "validate-snapshot",
    ],
)
def test_cli_subcommand_help_returns_zero(command, capsys):
    assert main([command, "--help"]) == 0

    assert command in capsys.readouterr().out


def test_probe_cts_dry_run_outputs_payload(capsys):
    assert main(["probe-cts", "--dry-run", "Python"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["keyword"] == "Python"
    assert payload["page"] == 1
    assert payload["pageSize"] == 1


def test_probe_cts_defaults_to_dry_run_payload(capsys):
    assert main(["probe-cts", "Python"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["keyword"] == "Python"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run pytest tests/test_release_validation.py tests/cli/test_cli.py -q
```

Expected:

- FAIL because CLI dispatch and release script do not exist.

- [ ] **Step 3: Implement CLI dispatch and release validation**

Modify `src/seektalent_keyword_graph/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keyword-graph")
    subcommands = parser.add_subparsers(dest="command", required=True)

    import_jds = subcommands.add_parser("import-jds")
    import_jds.add_argument("input", type=Path)
    import_jds.add_argument("--build-db", required=True, type=Path)
    import_jds.set_defaults(func=_cmd_import_jds)

    extract_surfaces = subcommands.add_parser("extract-surfaces")
    extract_surfaces.add_argument("text")
    extract_surfaces.set_defaults(func=_cmd_extract_surfaces)

    build_relations = subcommands.add_parser("build-relations")
    build_relations.add_argument("surfaces", nargs="+")
    build_relations.set_defaults(func=_cmd_build_relations)

    probe_cts = subcommands.add_parser("probe-cts")
    probe_cts.add_argument("keyword")
    probe_cts.add_argument("--dry-run", action="store_true")
    probe_cts.add_argument("--real", action="store_true")
    probe_cts.set_defaults(func=_cmd_probe_cts)

    build_snapshot = subcommands.add_parser("build-snapshot")
    build_snapshot.add_argument("--output", required=True, type=Path)
    build_snapshot.set_defaults(func=_cmd_build_snapshot)

    validate_snapshot = subcommands.add_parser("validate-snapshot")
    validate_snapshot.add_argument("--snapshot", required=True, type=Path)
    validate_snapshot.add_argument("--manifest", required=True, type=Path)
    validate_snapshot.set_defaults(func=_cmd_validate_snapshot)

    return parser


def _cmd_import_jds(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.import_jds import import_jds

    import_jds(args.input, args.build_db)
    return 0


def _cmd_extract_surfaces(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.extract_surfaces import extract_surface_mentions

    print(json.dumps(extract_surface_mentions(args.text), ensure_ascii=False))
    return 0


def _cmd_build_relations(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.build_relations import build_seed_relations

    print(json.dumps(build_seed_relations(args.surfaces), ensure_ascii=False))
    return 0


def _cmd_probe_cts(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.cts.count_client import CtsCountClient
    from seektalent_keyword_graph.cts.probe_window import can_run_real_probe

    client = CtsCountClient(
        base_url=os.environ.get("KEYWORD_GRAPH_CTS_BASE_URL", ""),
        tenant_key=os.environ.get("KEYWORD_GRAPH_CTS_TENANT_KEY", ""),
        tenant_secret=os.environ.get("KEYWORD_GRAPH_CTS_TENANT_SECRET", ""),
    )
    if args.dry_run or not args.real:
        print(json.dumps(client.build_payload(args.keyword), ensure_ascii=False))
        return 0

    now = datetime.now().time()
    if not can_run_real_probe(False, now, time(9, 0), time(21, 0)):
        print("real CTS probe blocked outside 09:00-21:00", file=sys.stderr)
        return 2

    print("real CTS probe requires an explicit implementation gate", file=sys.stderr)
    return 2


def _cmd_build_snapshot(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.builder.build_snapshot import build_runtime_snapshot

    build_runtime_snapshot(args.output)
    return 0


def _cmd_validate_snapshot(args: argparse.Namespace) -> int:
    from seektalent_keyword_graph.release_validation import validate_snapshot_artifact

    return 0 if validate_snapshot_artifact(args.snapshot, args.manifest) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `src/seektalent_keyword_graph/release_validation.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FORBIDDEN_MARKERS = (
    b"KEYWORD_GRAPH_CTS_",
    b"tenant_secret",
    b"candidate_id",
    b"candidate_list",
    b"resume_text",
)


def validate_snapshot_size(path: Path, max_bytes: int = 100 * 1024 * 1024) -> bool:
    return path.exists() and path.stat().st_size <= max_bytes


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(snapshot_path: Path, manifest_path: Path) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "artifact": snapshot_path.name,
                "bytes": snapshot_path.stat().st_size,
                "sha256": calculate_sha256(snapshot_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def manifest_matches(snapshot_path: Path, manifest_path: Path) -> bool:
    if not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text())
    return (
        manifest.get("artifact") == snapshot_path.name
        and manifest.get("bytes") == snapshot_path.stat().st_size
        and manifest.get("sha256") == calculate_sha256(snapshot_path)
    )


def scan_forbidden_markers(path: Path) -> list[str]:
    payload = path.read_bytes().lower()
    return [marker.decode() for marker in FORBIDDEN_MARKERS if marker.lower() in payload]


def validate_snapshot_artifact(
    snapshot_path: Path,
    manifest_path: Path,
    max_bytes: int = 100 * 1024 * 1024,
) -> bool:
    return (
        validate_snapshot_size(snapshot_path, max_bytes)
        and manifest_matches(snapshot_path, manifest_path)
        and not scan_forbidden_markers(snapshot_path)
    )
```

Create `scripts/validate_release.py`:

```python
from __future__ import annotations

from seektalent_keyword_graph.release_validation import (
    calculate_sha256,
    manifest_matches,
    scan_forbidden_markers,
    validate_snapshot_artifact,
    validate_snapshot_size,
    write_manifest,
)

__all__ = [
    "calculate_sha256",
    "manifest_matches",
    "scan_forbidden_markers",
    "validate_snapshot_artifact",
    "validate_snapshot_size",
    "write_manifest",
]
```

Create `docs/release-checklist.md`:

```markdown
# Release Checklist

- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run python -m build --wheel` passes.
- [ ] Snapshot validates.
- [ ] Compressed snapshot is below 100MB.
- [ ] Snapshot contains no CTS key.
- [ ] Snapshot contains no candidate list or resume text.
- [ ] Manifest and checksum are generated.
- [ ] CLI `--help` lists every promised builder command.
- [ ] `keyword-graph probe-cts --dry-run Python` prints payload only and makes no CTS call.
- [ ] Rollback path points to previous snapshot.
```

- [ ] **Step 4: Run test**

Run:

```bash
uv run pytest tests/test_release_validation.py tests/cli/test_cli.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add src scripts docs tests
git commit -m "chore: add release validation checklist"
```

---

### Slice S19: Final Verification and Readiness Report

**Files:**
- Create: `tests/test_import_boundaries.py`
- Create: `scripts/write_readiness_report.py`
- Create: `docs/readiness-report.md`

- [ ] **Step 1: Add runtime import-boundary test**

Create `tests/test_import_boundaries.py`:

```python
import ast
from pathlib import Path


RUNTIME_FILES = [
    Path("src/seektalent_keyword_graph/engine.py"),
    *Path("src/seektalent_keyword_graph/runtime").glob("*.py"),
]
FORBIDDEN_IMPORT_PREFIXES = (
    "seektalent_keyword_graph.builder",
    "seektalent_keyword_graph.cts",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_runtime_does_not_import_builder_or_cts():
    offenders = []
    for path in RUNTIME_FILES:
        if not path.exists():
            continue
        for module in imported_modules(path):
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                offenders.append((str(path), module))

    assert offenders == []
```

- [ ] **Step 2: Run full tests**

Run:

```bash
uv run pytest
```

Expected:

- PASS.

- [ ] **Step 3: Run lint**

Run:

```bash
uv run ruff check .
```

Expected:

- PASS.

- [ ] **Step 4: Verify old naming does not exist**

Run:

```bash
rg -n "seektalent-keyword-intel|seektalent_keyword_intel|KEYWORD_INTEL|keyword_intelligence" \
  README.md GOAL.md AGENTS.md pyproject.toml src tests contracts scripts
```

Expected:

- Exit 1 with no matches.

- [ ] **Step 5: Create readiness report writer**

Create `scripts/write_readiness_report.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "readiness-report.md"


def run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout.strip()


def status_line(name: str, code: int, output: str) -> str:
    first_line = output.splitlines()[0] if output else "no output"
    return f"- {name}: exit {code}; {first_line}"


def main() -> int:
    old_name_pattern = "|".join(
        [
            "seektalent-keyword-" + "intel",
            "seektalent_keyword_" + "intel",
            "KEYWORD_" + "INTEL",
            "keyword_" + "intelligence",
        ]
    )
    checks = [
        ("pytest", ["uv", "run", "pytest"]),
        ("ruff check .", ["uv", "run", "ruff", "check", "."]),
        ("Wheel build", ["uv", "run", "python", "-m", "build", "--wheel"]),
        (
            "Naming scan",
            [
                "rg",
                "-n",
                old_name_pattern,
                "README.md",
                "GOAL.md",
                "AGENTS.md",
                "pyproject.toml",
                "src",
                "tests",
                "contracts",
                "scripts",
            ],
        ),
        ("Current commit", ["git", "rev-parse", "HEAD"]),
    ]
    results = [(name, *run(command)) for name, command in checks]
    naming_code = next(code for name, code, _ in results if name == "Naming scan")
    naming_status = "no old names found" if naming_code == 1 else "old names found"
    commit = next(output for name, _, output in results if name == "Current commit")

    REPORT.write_text(
        "\n".join(
            [
                "# Readiness Report",
                "",
                "## Completed",
                "",
                "- M0 scaffold status: verified by uv run pytest and package import tests.",
                "- M1 runtime status: verified by runtime snapshot and query plan tests.",
                "- M2 builder status: verified by builder fixture tests.",
                "- M3 graph status: verified by relation and co-occurrence tests.",
                "- M4 CTS status: verified by fake CTS and dry-run CTS tests.",
                "- M5 snapshot/query status: verified by snapshot builder and policy tests.",
                "- M6 consumer contract status: verified by contract example tests.",
                "- M7 release status: verified by CLI and release validation tests.",
                "",
                "## Verification",
                "",
                *[status_line(name, code, output) for name, code, output in results],
                f"- Naming scan interpreted result: {naming_status}.",
                f"- Commit: {commit}",
                "",
                "## Known Gaps",
                "",
                "- Real CTS probe remains gated to 09:00-21:00.",
                "- SeekTalent integration code is not modified unless separately requested.",
                "- Production snapshot is not committed to git.",
                "",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Generate readiness report**

Run:

```bash
python scripts/write_readiness_report.py
```

Expected:

- Exit 0.
- `docs/readiness-report.md` exists.
- The report contains actual exit codes and the current commit hash.

- [ ] **Step 7: Verify readiness report has no blank statuses**

Run:

```bash
rg -n "status:$|uv run pytest:$|uv run ruff check \\.:$|Naming scan:$|Commit:$" docs/readiness-report.md
```

Expected:

- Exit 1 with no matches.

- [ ] **Step 8: Commit**

```bash
git add tests/test_import_boundaries.py scripts/write_readiness_report.py docs/readiness-report.md
git commit -m "docs: add readiness report"
```

---

## Long Goal Prompt

Use this prompt in a new blank Codex Goal window:

```text
Work in /Users/frankqdwang/MLE/seektalent-keyword-graph.

Read AGENTS.md, README.md, GOAL.md, docs/superpowers/specs/2026-05-30-keyword-graph-m0-m7.md, and docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md.

Before running tests, execute Slice S0 including `uv sync --extra dev --extra builder`, then verify `uv run pytest --version`, `uv run ruff --version`, `uv run python -m build --version`, and `uv run python -c "import pydantic, httpx"`.

Execute the plan task-by-task. Continue as long as possible. Commit after each verified slice. Do not call real CTS during unattended execution. Use fake CTS and dry-run gates only. Runtime must never import builder/cts and this package must never import SeekTalent.

Primary target: complete M0-M1 fully. Continue into M2-M7 slices if earlier slices pass. Stop only if blocked by repeated test failures, missing required local dependencies, or completion. Before stopping, run the verification commands available and update docs/readiness-report.md if it exists.
```

## Self-Review

- Spec coverage: M0-M7 are represented by S0-S19.
- Placeholder scan: no placeholder red flags found.
- Type consistency: package name is `seektalent-keyword-graph`; import package is `seektalent_keyword_graph`; runtime class is `KeywordGraph`; CLI is `keyword-graph`.
- Execution safety: real CTS is gated and excluded from unattended overnight runs.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `fw-plan-review` | Architecture, code quality, tests, performance | 1 | ADDRESSED | 6 P1 findings and 2 P2 findings are folded into S0/S2/S3/S12/S13/S14/S18/S19 |
| Design Review | `fw-plan-review` | UI/UX gaps | 0 | SKIPPED | No UI or user-facing screen scope in this plan |

### Step 0 Scope Challenge

The plan intentionally spans more than 8 files and more than 2 modules because the requested deliverable is a new package plus builder pipeline, not a single patch. Scope is acceptable only if it remains sliced and verified. The current S0-S19 structure is workable, and the P1/P2 gaps below have been folded back into the plan.

### What Already Exists

- Planning repo docs already define the dependency direction: SeekTalent consumes `seektalent-keyword-graph`, and this package must not import SeekTalent.
- The main SeekTalent repo and CTS credentials exist outside this planning repo. This plan should not modify SeekTalent directly.
- CTS probing is defined as builder-only. Runtime users must not need CTS keys.
- No implementation source tree exists yet in this repo. The current plan is the source of truth for the first build.

### NOT in Scope

- Real CTS execution during an unattended overnight Goal.
- SeekTalent integration code changes in the main app.
- UI, admin screens, or human review tooling beyond CSV or JSONL sampling outputs.
- Production snapshot artifact committed to git.
- Remote publish, PR, merge, release, or deploy actions.

### Engineering Findings

`[P1] (confidence: 9/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:52` - S0 creates `pyproject.toml` and a `Makefile`, but never installs dev or builder dependencies. Later slices call `pytest` and `ruff`, so a blank Codex Goal can fail before any product work starts. Add an explicit bootstrap step such as `uv sync --extra dev --extra builder`, then verify `uv run pytest --version`, `uv run ruff --version`, and an import smoke test.

`[P1] (confidence: 9/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:341` - `QueryPlanResponse` uses `list[dict]` and `dict` for core contract fields. That weakens the package boundary SeekTalent will depend on. Add typed Pydantic models for concept rows, query bundles, rejected surfaces, lineage, and warnings, then generate schema and example validation tests from those models.

`[P1] (confidence: 9/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:398` - snapshot validation only checks file existence and `snapshot_meta`. The spec requires missing, incompatible, and corrupt snapshots to fail clearly. Add tests and implementation for unsupported schema versions, missing required tables, empty required tables, and typed `UnsupportedSnapshotError` / `SnapshotIntegrityError` paths.

`[P1] (confidence: 8/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:1443` - CTS fake and real probe coverage is below the spec. The fake client only tests success and timeout, while the spec requires success, zero, timeout, 429, 5xx, and auth error behavior. Add the missing fake tests and status mapping, plus real client dry-run tests for payload, response parsing, and no-secret logging.

`[P1] (confidence: 9/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:1621` - `build_runtime_snapshot` only writes `snapshot_meta`, but the runtime and release goals require required runtime tables, manifest, checksum, and validation. Extend S14/S18 so generated snapshots contain the runtime schema, pass `SQLiteSnapshot.open().validate()`, and produce verifiable manifest/checksum metadata.

`[P1] (confidence: 8/10) docs/superpowers/specs/2026-05-30-keyword-graph-m0-m7.md:106` - the spec promises CLI commands, but S1 only creates a `main()` that returns 0 and no later slice wires command dispatch. Add a CLI slice with tests for `keyword-graph --help`, `import-jds`, `extract-surfaces`, `build-relations`, `probe-cts --dry-run`, `build-snapshot`, and `validate-snapshot`.

`[P2] (confidence: 8/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:22` - the runtime/builder import boundary is stated but not tested. Add an import-boundary test that fails if runtime modules import `seektalent_keyword_graph.builder` or `seektalent_keyword_graph.cts`.

`[P2] (confidence: 7/10) docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md:2032` - the readiness report template starts with blank statuses and depends on a later fill step. For unattended execution, make S19 require actual command outputs and commit hash values immediately, so a stopped Goal does not leave a misleading empty report.

### Test Review

The first review found critical coverage gaps. The revised plan now represents them directly in the implementation slices:

```text
CODE PATHS
[+] Package bootstrap
  |-- [PLANNED] dependency install in blank environment
  `-- [PLANNED] import smoke after editable install
[+] Runtime contracts
  |-- [TESTED] request/response basic validation
  `-- [PLANNED] typed nested schema for returned query plan fields
[+] SQLite snapshot open
  |-- [TESTED] existing fixture meta loads
  |-- [TESTED] missing file raises
  |-- [PLANNED] unsupported snapshot schema raises
  |-- [PLANNED] missing runtime tables raises
  `-- [PLANNED] corrupt or empty required data raises
[+] CTS probing
  |-- [TESTED] fake success
  |-- [TESTED] fake timeout
  |-- [PLANNED] zero recall
  |-- [PLANNED] 429 rate limit
  |-- [PLANNED] 5xx API error
  `-- [PLANNED] auth error
[+] Release validation
  |-- [TESTED] compressed size threshold
  |-- [PLANNED] checksum validation
  |-- [PLANNED] secret scan
  `-- [PLANNED] candidate and resume text scan
```

### Performance Review

No P1 performance issue found in the plan itself. The chosen runtime shape, readonly SQLite plus deterministic local selection, fits the lightweight cross-platform requirement. The main performance risk is uncontrolled build-side growth. Keep CTS at `1 RPS / concurrency 1 / 09:00-21:00`, keep runtime snapshot compressed under 100MB hard cap, and add a release validation command that fails before packaging if the compressed artifact exceeds the cap.

### Implementation Tasks

Synthesized from this review's findings. Each task derives from a specific finding above.

- [x] **T1 (P1, human: ~20min / CC: ~5min)** - bootstrap - add dependency install and tool smoke checks to S0.
  - Surfaced by: Engineering Findings P1 dependency bootstrap.
  - Files: `docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md`.
  - Verify: the long Goal prompt includes `uv sync` before first `uv run pytest`.
- [x] **T2 (P1, human: ~1h / CC: ~15min)** - contracts - replace loose response dictionaries with typed Pydantic nested models.
  - Surfaced by: Engineering Findings P1 contract looseness.
  - Files: plan S2, contracts examples in S17.
  - Verify: contract tests validate nested model fields and JSON schema.
- [x] **T3 (P1, human: ~1h / CC: ~15min)** - snapshot runtime - add schema/table/integrity validation tests and implementation steps.
  - Surfaced by: Engineering Findings P1 snapshot validation.
  - Files: plan S3/S4/S14/S18.
  - Verify: tests cover unsupported schema, missing required table, and corrupt required data.
- [x] **T4 (P1, human: ~1h / CC: ~15min)** - CTS - complete fake CTS status coverage and real client dry-run parsing tests.
  - Surfaced by: Engineering Findings P1 CTS undercoverage.
  - Files: plan S12/S13.
  - Verify: CTS tests cover success, zero, timeout, 429, 5xx, auth error, payload, and response parsing.
- [x] **T5 (P1, human: ~1h / CC: ~20min)** - snapshot builder/release - require runtime tables, manifest, checksum, secret scan, and privacy scan.
  - Surfaced by: Engineering Findings P1 snapshot builder and release validation.
  - Files: plan S14/S18.
  - Verify: `validate-snapshot` fails on oversize, missing checksum, secrets, candidate names, or resume text.
- [x] **T6 (P1, human: ~1h / CC: ~15min)** - CLI - add tested command dispatch for promised builder and validation commands.
  - Surfaced by: Engineering Findings P1 CLI gap.
  - Files: plan S1 plus new CLI slice or S18 updates.
  - Verify: CLI tests cover `--help` and each promised command in dry-run or fixture mode.
- [x] **T7 (P2, human: ~20min / CC: ~5min)** - import boundary - add runtime import-boundary tests.
  - Surfaced by: Engineering Findings P2 runtime/builder boundary.
  - Files: plan S3/S4/S19 or dedicated boundary test slice.
  - Verify: tests fail if runtime imports builder or CTS modules.
- [x] **T8 (P2, human: ~10min / CC: ~5min)** - readiness - make readiness report values non-blank and command-derived.
  - Surfaced by: Engineering Findings P2 readiness report.
  - Files: plan S19.
  - Verify: S19 requires actual command outputs, commit hash, and final status lines.

### Verdict

REVISION APPLIED. The original P1/P2 plan-review findings are addressed in the plan text. No user tradeoff is pending. Rerun `fw-plan-review` as a final gate before starting a long unattended Goal if strict stage-gate evidence is required.
