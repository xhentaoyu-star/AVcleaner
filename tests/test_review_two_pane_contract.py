from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_review_layout_uses_responsive_two_pane_grid() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert 'class="review-layout"' in html
    assert ".review-layout" in css
    assert "minmax(560px, 1fr) clamp(320px, 30vw, 460px)" in css
    assert "68%" not in css
    assert "32%" not in css


def test_review_detail_panel_is_inside_review_layout() -> None:
    html = HTML.read_text(encoding="utf-8")

    review_block = html[html.index('class="review-layout"') : html.index('id="executionSummaryBtn"')]
    assert 'class="preview-table review-table"' in review_block
    assert 'class="detail-panel detail-drawer"' in review_block
