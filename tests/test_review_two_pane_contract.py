from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_review_layout_uses_responsive_two_pane_grid() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert 'class="review-workbench review-layout"' in html
    assert ".review-workbench" in css
    assert "minmax(760px, 1fr) 360px" in css
    assert "@media (min-width: 1540px)" in css
    assert "68%" not in css
    assert "32%" not in css


def test_review_detail_panel_is_inside_review_layout() -> None:
    html = HTML.read_text(encoding="utf-8")

    review_block = html[html.index('class="review-workbench review-layout"') : html.index('data-zone="statusbar"')]
    assert 'class="preview-table review-table"' in review_block
    assert 'class="detail-panel detail-drawer detail-stack"' in review_block
