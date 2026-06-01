"""Runtime-only consumer configuration for the keyword graph package."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class KeywordGraphRuntimeSettings(BaseModel):
    """SeekTalent-side settings that never read builder or CTS configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    snapshot_path: Path | None = None
    snapshot_id: str | None = None
    fail_open: bool = True
    max_bundles: int = Field(default=5, ge=1, le=20)
    default_provider: str = "cts"
    max_alternatives: int = Field(default=5, ge=0, le=50)

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> KeywordGraphRuntimeSettings:
        """Load only SEEKTALENT_KEYWORD_GRAPH_* runtime settings."""

        env = os.environ if environ is None else environ
        return cls(
            enabled=_parse_bool(
                env.get("SEEKTALENT_KEYWORD_GRAPH_ENABLED"), default=True
            ),
            snapshot_path=_optional_path(
                env.get("SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_PATH")
            ),
            snapshot_id=_optional_str(env.get("SEEKTALENT_KEYWORD_GRAPH_SNAPSHOT_ID")),
            fail_open=_parse_bool(
                env.get("SEEKTALENT_KEYWORD_GRAPH_FAIL_OPEN"), default=True
            ),
            max_bundles=_parse_int(
                env.get("SEEKTALENT_KEYWORD_GRAPH_MAX_BUNDLES"), default=5
            ),
            default_provider=(
                _optional_str(
                    env.get("SEEKTALENT_KEYWORD_GRAPH_DEFAULT_PROVIDER")
                )
                or "cts"
            ),
            max_alternatives=_parse_int(
                env.get("SEEKTALENT_KEYWORD_GRAPH_MAX_ALTERNATIVES"), default=5
            ),
        )


def _optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_path(value: str | None) -> Path | None:
    stripped = _optional_str(value)
    if stripped is None:
        return None
    return Path(stripped)


def _parse_bool(value: str | None, *, default: bool) -> bool:
    stripped = _optional_str(value)
    if stripped is None:
        return default
    normalized = stripped.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _parse_int(value: str | None, *, default: int) -> int:
    stripped = _optional_str(value)
    if stripped is None:
        return default
    return int(stripped)
