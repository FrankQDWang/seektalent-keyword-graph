from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_build_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        create table if not exists jd_documents (
          jd_id text primary key,
          source text not null,
          source_ref text not null,
          title_raw text not null,
          jd_text text not null,
          content_hash text not null
        )
        """
    )
    return conn
