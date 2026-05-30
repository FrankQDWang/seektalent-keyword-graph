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
| S18 | M7 | Release validation and rollback docs |
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
	pytest

lint:
	ruff check .

check: lint test
```

- [ ] **Step 3: Create `.python-version`**

Use this content:

```text
3.12
```

- [ ] **Step 4: Run scaffold verification**

Run:

```bash
python3 -m pip --version
python3 -m compileall -q .
```

Expected:

- Both commands exit 0.

- [ ] **Step 5: Commit**

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
pytest tests/test_import.py -q
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
pytest tests/test_import.py -q
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
        concept_sheet=[],
        query_bundles=[],
        rejected_surfaces=[],
        lineage={"input_hash": "sha256:test"},
        warnings=[],
    )

    dumped = response.model_dump()
    assert dumped["schema_version"] == "query-plan-response-v1"
    assert dumped["kg_snapshot_id"] == "kg_test"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/contracts/test_query_plan_contract.py -q
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
    concept_sheet: list[dict] = Field(default_factory=list)
    query_bundles: list[dict] = Field(default_factory=list)
    rejected_surfaces: list[dict] = Field(default_factory=list)
    lineage: dict = Field(default_factory=dict)
    warnings: list[dict] = Field(default_factory=list)
```

Create `src/seektalent_keyword_graph/contracts/__init__.py`:

```python
from seektalent_keyword_graph.contracts.query_plan import (
    QueryPlanRequest,
    QueryPlanResponse,
    RequirementTerm,
)

__all__ = ["QueryPlanRequest", "QueryPlanResponse", "RequirementTerm"]
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
pytest tests/contracts/test_query_plan_contract.py -q
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
from pathlib import Path

import pytest

from seektalent_keyword_graph.runtime.errors import SnapshotUnavailableError
from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


FIXTURE = Path("tests/fixtures/snapshots/minimal.sqlite3")


def test_snapshot_meta_loads():
    snapshot = SQLiteSnapshot.open(FIXTURE)
    meta = snapshot.meta()

    assert meta["kg_snapshot_id"] == "kg_fixture"
    assert meta["snapshot_schema_version"] == "snapshot-v1"


def test_missing_snapshot_raises():
    with pytest.raises(SnapshotUnavailableError):
        SQLiteSnapshot.open("missing.sqlite3")
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/runtime/test_sqlite_snapshot.py -q
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

from seektalent_keyword_graph.runtime.errors import SnapshotUnavailableError


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
        return cls(snapshot_path, connection)

    def meta(self) -> dict[str, Any]:
        row = self.connection.execute(
            "select kg_snapshot_id, snapshot_schema_version, selection_policy_version "
            "from snapshot_meta limit 1"
        ).fetchone()
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
        insert into snapshot_meta values ('kg_fixture', 'snapshot-v1', 'policy-v1');
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
pytest tests/runtime/test_sqlite_snapshot.py -q
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
pytest tests/runtime/test_keyword_graph_lookup.py -q
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
pytest tests/runtime/test_keyword_graph_lookup.py tests/runtime/test_sqlite_snapshot.py -q
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
    assert response.query_bundles[0]["bundle_type"] == "anchor"
    assert response.query_bundles[0]["queries"][0]["query_text"] == "k8s"


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

    assert response.query_bundles[0]["bundle_type"] == "fallback"
    assert response.warnings[0]["code"] == "no_snapshot_surface_match"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/runtime/test_build_query_plan.py -q
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
pytest tests/runtime/test_build_query_plan.py tests/runtime -q
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
pytest tests/builder/test_import_jds.py -q
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
pytest tests/builder/test_import_jds.py -q
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
pytest tests/builder/test_sections.py -q
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
pytest tests/builder/test_sections.py -q
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
pytest tests/builder/test_extract_surfaces.py -q
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
pytest tests/builder/test_extract_surfaces.py -q
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
pytest tests/domain/test_normalization.py -q
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
pytest tests/domain/test_normalization.py -q
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
pytest tests/builder/test_build_relations.py -q
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
pytest tests/builder/test_build_relations.py -q
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
pytest tests/builder/test_reports.py -q
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
pytest tests/builder/test_reports.py -q
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
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/cts/test_fake_client.py -q
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
        return {"query_text": query_text, "total": int(value), "status": "success"}
```

- [ ] **Step 4: Run test**

Run:

```bash
pytest tests/cts/test_fake_client.py -q
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

- [ ] **Step 1: Write probe window tests**

Create `tests/cts/test_probe_window.py`:

```python
from datetime import time

from seektalent_keyword_graph.cts.probe_window import is_within_probe_window


def test_probe_window_allows_daytime():
    assert is_within_probe_window(time(10, 0), time(9, 0), time(21, 0))


def test_probe_window_blocks_night():
    assert not is_within_probe_window(time(22, 0), time(9, 0), time(21, 0))
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/cts/test_probe_window.py -q
```

Expected:

- FAIL because probe window module does not exist.

- [ ] **Step 3: Implement probe window**

Create `src/seektalent_keyword_graph/cts/probe_window.py`:

```python
from __future__ import annotations

from datetime import time


def is_within_probe_window(now: time, start: time, end: time) -> bool:
    return start <= now < end
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

    def build_payload(self, keyword: str) -> dict:
        return {"keyword": keyword, "page": 1, "pageSize": 1}
```

- [ ] **Step 5: Run tests**

Run:

```bash
pytest tests/cts -q
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
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/builder/test_build_snapshot.py -q
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
        insert into snapshot_meta values ('kg_generated_fixture', 'snapshot-v1', 'policy-v1');
        """
    )
    conn.close()
```

- [ ] **Step 4: Run test**

Run:

```bash
pytest tests/builder/test_build_snapshot.py -q
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
pytest tests/domain/test_policies.py -q
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
pytest tests/domain/test_policies.py -q
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
pytest tests/observability/test_replay_report.py -q
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
pytest tests/observability/test_replay_report.py -q
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
pytest tests/contracts -q
```

Expected:

- PASS.

- [ ] **Step 4: Commit**

```bash
git add contracts tests
git commit -m "test: add consumer contract examples"
```

---

### Slice S18: Release Validation and Rollback Docs

**Files:**
- Create: `scripts/validate_release.py`
- Create: `docs/release-checklist.md`
- Test: `tests/test_release_validation.py`

- [ ] **Step 1: Write release validation test**

Create `tests/test_release_validation.py`:

```python
from scripts.validate_release import validate_snapshot_size


def test_validate_snapshot_size_allows_small_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"small")

    assert validate_snapshot_size(path, max_bytes=100)


def test_validate_snapshot_size_rejects_large_file(tmp_path):
    path = tmp_path / "snapshot.sqlite3.gz"
    path.write_bytes(b"large")

    assert not validate_snapshot_size(path, max_bytes=3)
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_release_validation.py -q
```

Expected:

- FAIL because script does not exist.

- [ ] **Step 3: Implement release validation**

Create `scripts/validate_release.py`:

```python
from __future__ import annotations

from pathlib import Path


def validate_snapshot_size(path: Path, max_bytes: int = 100 * 1024 * 1024) -> bool:
    return path.exists() and path.stat().st_size <= max_bytes
```

Create `docs/release-checklist.md`:

```markdown
# Release Checklist

- [ ] `pytest` passes.
- [ ] `ruff check .` passes.
- [ ] Wheel builds.
- [ ] Snapshot validates.
- [ ] Compressed snapshot is below 100MB.
- [ ] Snapshot contains no CTS key.
- [ ] Snapshot contains no candidate list or resume text.
- [ ] Manifest and checksum are generated.
- [ ] Rollback path points to previous snapshot.
```

- [ ] **Step 4: Run test**

Run:

```bash
pytest tests/test_release_validation.py -q
```

Expected:

- PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts docs tests
git commit -m "chore: add release validation checklist"
```

---

### Slice S19: Final Verification and Readiness Report

**Files:**
- Create: `docs/readiness-report.md`

- [ ] **Step 1: Run full tests**

Run:

```bash
pytest
```

Expected:

- PASS.

- [ ] **Step 2: Run lint**

Run:

```bash
ruff check .
```

Expected:

- PASS.

- [ ] **Step 3: Verify old naming does not exist**

Run:

```bash
rg -n "seektalent-keyword-intel|seektalent_keyword_intel|KEYWORD_INTEL|keyword_intelligence" .
```

Expected:

- Exit 1 with no matches.

- [ ] **Step 4: Write readiness report**

Create `docs/readiness-report.md`:

```markdown
# Readiness Report

## Completed

- M0 scaffold status:
- M1 runtime status:
- M2 builder status:
- M3 graph status:
- M4 CTS status:
- M5 snapshot/query status:
- M6 consumer contract status:
- M7 release status:

## Verification

- `pytest`:
- `ruff check .`:
- Naming scan:

## Known Gaps

- Real CTS probe remains gated to 09:00-21:00.
- SeekTalent integration code is not modified unless separately requested.
- Production snapshot is not committed to git.
```

- [ ] **Step 5: Fill report with actual command outputs**

Edit `docs/readiness-report.md` and replace each blank status with the actual result from this run.

- [ ] **Step 6: Commit**

```bash
git add docs/readiness-report.md
git commit -m "docs: add readiness report"
```

---

## Long Goal Prompt

Use this prompt in a new blank Codex Goal window:

```text
Work in /Users/frankqdwang/MLE/seektalent-keyword-graph.

Read AGENTS.md, README.md, GOAL.md, docs/superpowers/specs/2026-05-30-keyword-graph-m0-m7.md, and docs/superpowers/plans/2026-05-30-keyword-graph-m0-m7.md.

Execute the plan task-by-task. Continue as long as possible. Commit after each verified slice. Do not call real CTS during unattended execution. Use fake CTS and dry-run gates only. Runtime must never import builder/cts and this package must never import SeekTalent.

Primary target: complete M0-M1 fully. Continue into M2-M7 slices if earlier slices pass. Stop only if blocked by repeated test failures, missing required local dependencies, or completion. Before stopping, run the verification commands available and update docs/readiness-report.md if it exists.
```

## Self-Review

- Spec coverage: M0-M7 are represented by S0-S19.
- Placeholder scan: the plan contains no `TBD`, `TODO`, or `implement later`.
- Type consistency: package name is `seektalent-keyword-graph`; import package is `seektalent_keyword_graph`; runtime class is `KeywordGraph`; CLI is `keyword-graph`.
- Execution safety: real CTS is gated and excluded from unattended overnight runs.
