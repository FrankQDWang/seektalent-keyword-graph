from __future__ import annotations

import hashlib
import json
from pathlib import Path

from seektalent_keyword_graph.builder.build_store import connect_build_db


def import_jds(jsonl_path: Path, db_path: Path) -> int:
    conn = connect_build_db(db_path)
    count = 0
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        content = item["jd_text"]
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        jd_id = f"{item['source']}:{item['source_ref']}"
        conn.execute(
            """
            insert or replace into jd_documents
            (jd_id, source, source_ref, title_raw, jd_text, content_hash)
            values (?, ?, ?, ?, ?, ?)
            """,
            (jd_id, item["source"], item["source_ref"], item["title_raw"], content, digest),
        )
        count += 1
    conn.commit()
    conn.close()
    return count
