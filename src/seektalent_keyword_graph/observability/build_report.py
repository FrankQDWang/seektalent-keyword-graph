"""Build and extraction summary reports."""

from __future__ import annotations

from typing import Any

from seektalent_keyword_graph.builder.build_store import BuildStore


def generate_extraction_report(
    store: BuildStore, *, import_report: Any | None = None
) -> dict[str, object]:
    """Generate a deterministic extraction report from persisted build state."""
    counts = {
        "jd_documents": _count(store, "jd_documents"),
        "jd_sections": _count(store, "jd_sections"),
        "keyword_mentions": _count(store, "keyword_mentions"),
        "surfaces": _count(store, "surfaces"),
        "blocked_candidates": _count(store, "blocked_surface_candidates"),
        "import_errors": len(import_report.errors) if import_report is not None else 0,
        "duplicates": import_report.duplicate_count if import_report is not None else 0,
    }
    top_surfaces = [
        {
            "text_norm": row["text_norm"],
            "display_text": row["display_text"],
            "jd_df": row["jd_df"],
            "jd_tf_total": row["jd_tf_total"],
        }
        for row in store.connection.execute(
            """
            select text_norm, display_text, jd_df, jd_tf_total
            from surfaces
            order by jd_df desc, jd_tf_total desc, text_norm
            limit 10
            """
        ).fetchall()
    ]
    blocked_reason_summary = {
        row["reason_code"]: row["count"]
        for row in store.connection.execute(
            """
            select reason_code, count(*) as count
            from blocked_surface_candidates
            group by reason_code
            order by reason_code
            """
        ).fetchall()
    }
    failed_records = import_report.errors if import_report is not None else []
    return {
        "counts": counts,
        "top_surfaces": top_surfaces,
        "blocked_reason_summary": blocked_reason_summary,
        "failed_records": failed_records,
    }


def _count(store: BuildStore, table: str) -> int:
    row = store.connection.execute(f"select count(*) as count from {table}").fetchone()
    return int(row["count"])
