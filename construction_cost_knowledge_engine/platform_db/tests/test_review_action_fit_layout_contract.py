from __future__ import annotations

from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


def source(name: str) -> str:
    return (WEB_ROOT / name).read_text(encoding="utf-8")


def test_mapping_action_cell_contract() -> None:
    script = source("static/review.js")
    component = script[script.index("class MappingActionCell"):script.index("function renderMappings")]
    for token in (
        "mapping_draft.create", "mapping_draft.update", "mapping_draft.exclude",
        'row_origin==="draft_copy"', "data-required-permission", 'aria-label="',
        "data-disabled-reason", "Copy", "Move", "Exclude", "Restore",
    ):
        assert token in component
    assert "administrator" not in component
    assert "allBills" in script
    assert "state.allBills.filter" in script


def test_layout_controls_and_storage_contract() -> None:
    markup = source("review.html")
    script = source("static/review.js")
    assert 'id="layoutMode"' in markup
    assert 'id="reviewDensity"' in markup
    for mode in ("auto_fit", "full_columns", "compact_review"):
        assert mode in markup and mode in script
    for key in (
        "review_layout_mode", "review_density", "left_pane_width",
        "right_pane_width", "top_pane_height",
    ):
        assert key in script
    assert "ResizeObserver(refreshResponsiveLayout)" in script


def test_candidate_table_fit_contract() -> None:
    markup = source("review.html")
    styles = source("static/review.css")
    assert "review-center-pane" in markup
    assert "candidate-table-container" in markup
    for token in (
        ".review-center-pane{min-width:0;width:100%;overflow:hidden}",
        ".candidate-table-container{width:100%;max-width:100%;min-width:0",
        '[data-layout-mode="full_columns"]',
        '[data-layout-mode="compact_review"]',
        ".mapping-table .action-column{position:sticky;right:0;width:120px",
    ):
        assert token in styles
