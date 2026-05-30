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
