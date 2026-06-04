from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


def load_run_fixture_flow() -> Any:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "run_fixture_flow.py"
    )
    spec = importlib.util.spec_from_file_location("run_fixture_flow", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load fixture flow script: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.run_fixture_flow
