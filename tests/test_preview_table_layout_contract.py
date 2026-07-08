from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_preview_table_uses_stable_columns_and_internal_scroll() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert 'class="preview-table review-table"' in html
    assert 'class="review-workbench review-layout"' in html
    assert "<colgroup>" in html
    for column in [
        "col-select",
        "col-status",
        "col-original",
        "col-target",
        "col-source",
        "col-review",
        "col-risk",
        "col-actions",
    ]:
        assert column in html
    assert "col-ai" not in html
    assert "AI/规则状态" not in html
    assert "table-layout: fixed" in css
    assert "overflow: auto" in css
    assert "text-overflow: ellipsis" in css
    assert "grid-template-columns: minmax(760px, 1fr) 380px" in css


def test_preview_rows_move_long_content_out_of_table_body() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "function renderIssueSummary" in text
    assert "function renderDetailDrawer" in text
    assert "body.append(detailRow(item))" not in text
    assert "review-summary two-line" in text
    assert "truncate" in text
    assert "cellLlmSuggestion(item)" not in text
    assert 'summary.textContent = "Debug 信息"' in text
    assert "renderTraceList(item)" in text
    assert "JSON.stringify(item" in text
