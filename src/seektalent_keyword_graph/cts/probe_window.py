from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REAL_CTS_GATE_TOKEN = "REAL_CTS_ALLOWED_FOR_KEYWORD_GRAPH"


class RealProbeGateError(RuntimeError):
    """Raised when real CTS probe execution is not explicitly allowed."""


@dataclass(frozen=True)
class ProbeWindowConfig:
    timezone: str = "Asia/Shanghai"
    start_hour: int = 9
    end_hour: int = 21

    def __post_init__(self) -> None:
        if not 0 <= self.start_hour <= 23:
            raise ValueError("start_hour must be between 0 and 23")
        if not 1 <= self.end_hour <= 24:
            raise ValueError("end_hour must be between 1 and 24")
        if self.start_hour >= self.end_hour:
            raise ValueError("start_hour must be before end_hour")
        ZoneInfo(self.timezone)


def is_inside_probe_window(
    now: datetime, config: ProbeWindowConfig | None = None
) -> bool:
    effective_config = config or ProbeWindowConfig()
    local_now = _localize(now, effective_config.timezone)
    return effective_config.start_hour <= local_now.hour < effective_config.end_hour


def validate_real_probe_gate(gate_file: str | Path | None) -> str:
    if gate_file is None:
        raise RealProbeGateError("real CTS probe mode requires a gate file")

    path = Path(gate_file)
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
    except FileNotFoundError as exc:
        raise RealProbeGateError("real CTS probe gate file does not exist") from exc
    except IndexError as exc:
        raise RealProbeGateError("invalid CTS real-mode gate token") from exc

    if first_line != REAL_CTS_GATE_TOKEN:
        raise RealProbeGateError("invalid CTS real-mode gate token")
    return first_line


def ensure_real_probe_allowed(
    *,
    mode: str,
    gate_file: str | Path | None,
    now: datetime,
    window_config: ProbeWindowConfig | None = None,
) -> None:
    if mode != "real":
        return

    validate_real_probe_gate(gate_file)
    if not is_inside_probe_window(now, window_config):
        raise RealProbeGateError("real CTS probe is outside CTS probe window")


def _localize(now: datetime, timezone: str) -> datetime:
    zone = ZoneInfo(timezone)
    if now.tzinfo is None:
        return now.replace(tzinfo=zone)
    return now.astimezone(zone)
