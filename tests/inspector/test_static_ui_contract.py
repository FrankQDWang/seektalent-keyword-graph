from __future__ import annotations

from pathlib import Path

ASSET_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "seektalent_keyword_graph"
    / "inspector"
    / "assets"
)


def test_static_ui_renders_required_snapshot_recall_and_provenance_fields() -> None:
    index = (ASSET_ROOT / "index.html").read_text(encoding="utf-8")
    script = (ASSET_ROOT / "app.js").read_text(encoding="utf-8")

    for heading in (
        "<th>Provider</th>",
        "<th>Evidence Type</th>",
        "<th>Evidence Ref</th>",
    ):
        assert heading in index

    for required_source_field in (
        "URLSearchParams(window.location.search)",
        "applyUrlQueryParams",
        "metaPayload.snapshot.manifest_path",
        "metaPayload.meta.built_at",
        "metaPayload.providers.join",
        "payload.request.query_text",
        "observationRow.provider",
        "alternative.evidence_type",
        "alternative.evidence_ref",
        "recommendation.evidence_observation_ids",
    ):
        assert required_source_field in script


def test_static_ui_clears_stale_results_on_hard_errors_without_inner_html() -> None:
    script = (ASSET_ROOT / "app.js").read_text(encoding="utf-8")

    assert "function clearResults()" in script
    assert "clearResults();" in script
    assert "innerHTML" not in script
