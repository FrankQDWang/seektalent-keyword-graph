from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "seektalent_keyword_graph"


def production_python_files() -> list[Path]:
    assert SRC_ROOT.is_dir(), f"production source package is missing: {SRC_ROOT}"

    files = sorted(SRC_ROOT.rglob("*.py"))
    assert files, f"no production Python files found under {SRC_ROOT}"
    return files


def imported_modules(path: Path, source_root: Path = SRC_ROOT) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module)
            elif node.level > 0:
                base_module = resolve_relative_import(
                    path, node.level, node.module, source_root
                )
                if node.module:
                    modules.add(base_module)
                else:
                    modules.update(
                        f"{base_module}.{alias.name}" for alias in node.names
                    )

    return modules


def is_seektalent_import(module: str) -> bool:
    return module in {"SeekTalent", "seektalent"} or module.startswith(
        ("SeekTalent.", "seektalent.")
    )


def resolve_relative_import(
    path: Path, level: int, module: str | None, source_root: Path = SRC_ROOT
) -> str:
    package_parts = path.relative_to(source_root).with_suffix("").parts[:-1]
    if level > 1:
        package_parts = package_parts[: -(level - 1)]
    parts = ("seektalent_keyword_graph", *package_parts)
    if module:
        parts = (*parts, module)
    return ".".join(parts)


def runtime_import_boundary_paths() -> list[Path]:
    runtime_surface_files = {"__init__.py", "cli.py", "engine.py"}
    return [
        path
        for path in production_python_files()
        if path.name in runtime_surface_files
        or "runtime" in path.relative_to(SRC_ROOT).parts
    ]


def domain_import_boundary_paths() -> list[Path]:
    return [
        path
        for path in production_python_files()
        if "domain" in path.relative_to(SRC_ROOT).parts
    ]


def test_scanner_resolves_relative_root_alias_imports(tmp_path: Path) -> None:
    source_root = tmp_path / "seektalent_keyword_graph"
    source_root.mkdir()
    path = source_root / "_boundary_regression.py"
    path.write_text("from . import builder, cts\n", encoding="utf-8")

    assert imported_modules(path, source_root) >= {
        "seektalent_keyword_graph.builder",
        "seektalent_keyword_graph.cts",
    }


def test_seektalent_import_guard_blocks_lowercase_root_imports() -> None:
    assert is_seektalent_import("seektalent")
    assert is_seektalent_import("seektalent.client")


def test_runtime_boundary_paths_include_public_import_surfaces() -> None:
    assert {path.name for path in runtime_import_boundary_paths()} >= {
        "__init__.py",
        "cli.py",
        "engine.py",
    }


def test_production_code_does_not_import_seektalent() -> None:
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} imports {module}"
        for path in production_python_files()
        for module in imported_modules(path)
        if is_seektalent_import(module)
    ]

    assert offenders == []


def test_runtime_import_paths_do_not_reach_builder_or_cts() -> None:
    blocked_prefixes = (
        "seektalent_keyword_graph.builder",
        "seektalent_keyword_graph.cts",
    )

    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} imports {module}"
        for path in runtime_import_boundary_paths()
        for module in imported_modules(path)
        if module.startswith(blocked_prefixes)
    ]

    assert offenders == []


def test_runtime_import_paths_do_not_read_cts_environment() -> None:
    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} mentions KEYWORD_GRAPH_CTS_"
        for path in runtime_import_boundary_paths()
        if "KEYWORD_GRAPH_CTS_" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_domain_import_paths_do_not_reach_runtime_builder_or_cts() -> None:
    blocked_prefixes = (
        "seektalent_keyword_graph.runtime",
        "seektalent_keyword_graph.builder",
        "seektalent_keyword_graph.cts",
    )

    offenders = [
        f"{path.relative_to(PROJECT_ROOT)} imports {module}"
        for path in domain_import_boundary_paths()
        for module in imported_modules(path)
        if module.startswith(blocked_prefixes)
    ]

    assert offenders == []
