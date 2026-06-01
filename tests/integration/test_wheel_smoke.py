from __future__ import annotations

import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from _fixture_flow_loader import load_run_fixture_flow

run_fixture_flow = load_run_fixture_flow()


def test_built_wheel_installs_and_opens_fixture_snapshot(tmp_path: Path) -> None:
    fixture = run_fixture_flow(tmp_path / "fixture")
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(dist_dir),
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    wheels = sorted(dist_dir.glob("seektalent_keyword_graph-*.whl"))
    assert len(wheels) == 1

    venv_dir = tmp_path / "venv"
    uv = shutil.which("uv")
    assert uv is not None
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    subprocess.run(
        [
            uv,
            "venv",
            "--python",
            sys.executable,
            "--system-site-packages",
            str(venv_dir),
        ],
        check=True,
        cwd=tmp_path,
        env=env,
    )
    python = venv_dir / "bin" / "python"
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), str(wheels[0])],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    smoke_env = os.environ.copy()
    smoke_env["PYTHONPATH"] = sysconfig.get_paths()["purelib"]
    completed = subprocess.run(
        [
            str(python),
            "-c",
            _SMOKE_SCRIPT,
            str(fixture.snapshot_path),
            str(fixture.manifest_path),
        ],
        check=True,
        capture_output=True,
        cwd=tmp_path,
        env=smoke_env,
        text=True,
    )

    assert completed.stdout.strip() == "kg-eval-fixture"


_SMOKE_SCRIPT = r"""
import sys

from seektalent_keyword_graph.engine import KeywordGraph

graph = KeywordGraph.open(sys.argv[1], sys.argv[2])
try:
    print(graph.store.meta()["kg_snapshot_id"])
finally:
    graph.close()
"""
