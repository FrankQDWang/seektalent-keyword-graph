from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from seektalent_keyword_graph.cts.probe_window import (
    REAL_CTS_GATE_TOKEN,
    ProbeWindowConfig,
    RealProbeGateError,
    ensure_real_probe_allowed,
    is_inside_probe_window,
    validate_real_probe_gate,
)


def shanghai_at(hour: int) -> datetime:
    return datetime(2026, 6, 1, hour, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def test_default_probe_window_is_0900_to_2100_shanghai() -> None:
    config = ProbeWindowConfig()

    assert config.timezone == "Asia/Shanghai"
    assert config.start_hour == 9
    assert config.end_hour == 21
    assert is_inside_probe_window(shanghai_at(9), config)
    assert is_inside_probe_window(shanghai_at(20), config)
    assert not is_inside_probe_window(shanghai_at(8), config)
    assert not is_inside_probe_window(shanghai_at(21), config)


def test_outside_window_blocks_real_probe_but_allows_dry_run(tmp_path: Path) -> None:
    gate_file = tmp_path / "gate.txt"
    gate_file.write_text(f"{REAL_CTS_GATE_TOKEN}\n", encoding="utf-8")

    ensure_real_probe_allowed(
        mode="dry_run",
        gate_file=None,
        now=shanghai_at(22),
        window_config=ProbeWindowConfig(),
    )

    with pytest.raises(RealProbeGateError, match="outside CTS probe window"):
        ensure_real_probe_allowed(
            mode="real",
            gate_file=gate_file,
            now=shanghai_at(22),
            window_config=ProbeWindowConfig(),
        )


def test_real_probe_without_gate_file_fails_closed() -> None:
    with pytest.raises(RealProbeGateError, match="gate file"):
        ensure_real_probe_allowed(
            mode="real",
            gate_file=None,
            now=shanghai_at(10),
            window_config=ProbeWindowConfig(),
        )


def test_real_probe_with_invalid_gate_file_fails_closed(tmp_path: Path) -> None:
    gate_file = tmp_path / "gate.txt"
    gate_file.write_text("NOT_ALLOWED\n", encoding="utf-8")

    with pytest.raises(RealProbeGateError, match="invalid CTS real-mode gate token"):
        validate_real_probe_gate(gate_file)


def test_real_probe_with_valid_gate_file_is_allowed_inside_window(
    tmp_path: Path,
) -> None:
    gate_file = tmp_path / "gate.txt"
    gate_file.write_text(f"{REAL_CTS_GATE_TOKEN}\n", encoding="utf-8")

    assert validate_real_probe_gate(gate_file) == REAL_CTS_GATE_TOKEN
    ensure_real_probe_allowed(
        mode="real",
        gate_file=gate_file,
        now=shanghai_at(10),
        window_config=ProbeWindowConfig(),
    )
