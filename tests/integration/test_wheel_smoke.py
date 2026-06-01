from __future__ import annotations

import os
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from _fixture_flow_loader import load_run_fixture_flow

run_fixture_flow = load_run_fixture_flow()

RUNTIME_DEPENDENCY_PATHS = {
    "annotated-types": ("annotated_types",),
    "pydantic": ("pydantic",),
    "pydantic-core": ("pydantic_core",),
    "typing-extensions": ("typing_extensions.py",),
    "typing-inspection": ("typing_inspection",),
}


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
            str(venv_dir),
        ],
        check=True,
        cwd=tmp_path,
        env=env,
    )
    python = venv_dir / "bin" / "python"
    venv_site_packages = _venv_site_packages(python)
    _copy_runtime_dependencies(venv_site_packages)
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    smoke_env = os.environ.copy()
    smoke_env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            str(python),
            "-c",
            _SMOKE_SCRIPT,
            str(fixture.snapshot_path),
            str(fixture.manifest_path),
            str(Path(__file__).resolve().parents[2]),
        ],
        check=True,
        capture_output=True,
        cwd=tmp_path,
        env=smoke_env,
        text=True,
    )

    assert completed.stdout.strip() == "kg-eval-fixture"


def _venv_site_packages(python: Path) -> Path:
    completed = subprocess.run(
        [
            str(python),
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip())


def _copy_runtime_dependencies(target_site_packages: Path) -> None:
    for distribution_name, package_paths in RUNTIME_DEPENDENCY_PATHS.items():
        distribution = metadata.distribution(distribution_name)
        source_site_packages = Path(distribution.locate_file(""))
        shutil.copytree(
            distribution._path,
            target_site_packages / distribution._path.name,
        )
        for package_path in package_paths:
            source = source_site_packages / package_path
            destination = target_site_packages / package_path
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)


_SMOKE_SCRIPT = r"""
from pathlib import Path
import sys

import seektalent_keyword_graph
from seektalent_keyword_graph.engine import KeywordGraph

package_path = Path(seektalent_keyword_graph.__file__).resolve()
repo_root = Path(sys.argv[3]).resolve()
try:
    package_path.relative_to(repo_root)
except ValueError:
    pass
else:
    message = f"imported seektalent_keyword_graph from source tree: {package_path}"
    raise AssertionError(message)

graph = KeywordGraph.open(sys.argv[1], sys.argv[2])
try:
    print(graph.store.meta()["kg_snapshot_id"])
finally:
    graph.close()
"""
