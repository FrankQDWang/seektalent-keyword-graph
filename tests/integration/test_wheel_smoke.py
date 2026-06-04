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
    subprocess_env = os.environ.copy()
    subprocess_env["PIP_NO_INDEX"] = "1"
    subprocess_env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    subprocess_env["UV_NO_INDEX"] = "1"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(dist_dir),
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[2],
        env=subprocess_env,
    )
    wheels = sorted(dist_dir.glob("seektalent_keyword_graph-*.whl"))
    assert len(wheels) == 1

    venv_dir = tmp_path / "venv"
    uv = shutil.which("uv")
    assert uv is not None
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
        env=subprocess_env,
    )
    python = venv_dir / "bin" / "python"
    venv_site_packages = _venv_site_packages(python)
    _copy_runtime_dependencies(venv_site_packages)
    subprocess.run(
        [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheels[0])],
        check=True,
        cwd=tmp_path,
        env=subprocess_env,
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

    bundled_completed = subprocess.run(
        [
            str(python),
            "-c",
            _BUNDLED_SMOKE_SCRIPT,
            str(Path(__file__).resolve().parents[2]),
        ],
        check=True,
        capture_output=True,
        cwd=tmp_path,
        env=smoke_env,
        text=True,
    )

    assert bundled_completed.stdout.strip() == "kg-eval-fixture"


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
        _copy_distribution_metadata(distribution, target_site_packages)
        for package_path in package_paths:
            source = source_site_packages / package_path
            destination = target_site_packages / package_path
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)


def _copy_distribution_metadata(
    distribution: metadata.Distribution, target_site_packages: Path
) -> None:
    files = distribution.files
    assert files is not None
    dist_info_dirs = {
        file.parts[0]
        for file in files
        if file.parts and file.parts[0].endswith(".dist-info")
    }
    assert len(dist_info_dirs) == 1
    dist_info_dir = dist_info_dirs.pop()
    shutil.copytree(
        Path(distribution.locate_file(dist_info_dir)),
        target_site_packages / dist_info_dir,
    )


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


_BUNDLED_SMOKE_SCRIPT = r"""
from pathlib import Path
import sys

import seektalent_keyword_graph
from seektalent_keyword_graph.engine import KeywordGraph

package_path = Path(seektalent_keyword_graph.__file__).resolve()
repo_root = Path(sys.argv[1]).resolve()
try:
    package_path.relative_to(repo_root)
except ValueError:
    pass
else:
    message = f"imported seektalent_keyword_graph from source tree: {package_path}"
    raise AssertionError(message)

graph = KeywordGraph.open_default({})
try:
    print(graph.store.meta()["kg_snapshot_id"])
finally:
    graph.close()

guarded_graph = KeywordGraph.open_default(
    {"SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID": "kg-eval-fixture"}
)
guarded_graph.close()
"""
