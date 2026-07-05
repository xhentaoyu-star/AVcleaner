from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_review_summary_is_line_clamped() -> None:
    css = CSS.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert ".review-summary" in css
    assert "-webkit-line-clamp: 2" in css
    assert "review-summary two-line" in app_js


def test_visible_table_cells_do_not_include_full_debug_context() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    render_plan = text[text.index("function renderPlan") : text.index("function renderTrash")]

    assert "JSON.stringify(item" not in render_plan
    assert "renderTraceList(item)" not in render_plan
    assert "llm_reason" not in render_plan
    assert "original.title = item.relative_path || item.source_rel_path" in render_plan
