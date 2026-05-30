from __future__ import annotations

from pathlib import Path


class KeywordGraph:
    def __init__(self, snapshot_path: Path | None = None) -> None:
        self.snapshot_path = snapshot_path

    @classmethod
    def open(cls, snapshot_path: str | Path) -> KeywordGraph:
        return cls(Path(snapshot_path))
