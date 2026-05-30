from __future__ import annotations

from pathlib import Path
from typing import Any

from seektalent_keyword_graph.runtime.sqlite_snapshot import SQLiteSnapshot


class KeywordGraph:
    def __init__(self, snapshot: SQLiteSnapshot) -> None:
        self.snapshot = snapshot
        self.snapshot_path = snapshot.path

    @classmethod
    def open(cls, snapshot_path: str | Path) -> KeywordGraph:
        return cls(SQLiteSnapshot.open(snapshot_path))

    def lookup_surface(self, text: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from surfaces where text_norm = ? limit 1", (text.casefold(),)
        ).fetchone()
        return dict(row) if row else None

    def get_concept(self, concept_id: str) -> dict[str, Any] | None:
        row = self.snapshot.connection.execute(
            "select * from concepts where concept_id = ? limit 1", (concept_id,)
        ).fetchone()
        return dict(row) if row else None
