from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_review_table_simple_columns_are_decision_focused() -> None:
    html = HTML.read_text(encoding="utf-8")

    for column in ["col-select", "col-status", "col-original", "col-target", "col-source", "col-review", "col-actions"]:
        assert column in html
    assert 'data-debug-only data-debug-field="table-risk-column"' not in html


def test_review_table_cells_do_not_render_debug_payloads() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")
    render_plan = app_js[app_js.index("function renderPlan") : app_js.index("function renderTrash")]

    assert "item.source_path" not in render_plan
    assert "JSON.stringify(item" not in render_plan
    assert "renderTraceList(item)" not in render_plan
    assert "renderProcessSummary(item)" in render_plan
