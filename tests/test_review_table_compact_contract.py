from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_review_table_has_compact_visible_columns() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    for heading in ["状态", "原文件", "最终文件名", "来源", "处理摘要", "风险/提示", "操作"]:
        assert f"<th>{heading}</th>" in html
    for column in ["col-select", "col-status", "col-original", "col-target", "col-source", "col-review", "col-risk", "col-actions"]:
        assert column in html
    assert "table-layout: fixed" in css
    assert ".preview-table td" in css
    assert "max-height: 42px" in css


def test_main_table_keeps_debug_and_full_paths_out_of_cells() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    render_plan = text[text.index("function renderPlan") : text.index("function renderTrash")]

    assert "JSON.stringify(item" not in render_plan
    assert "renderTraceList(item)" not in render_plan
    assert "item.source_path" not in render_plan
    assert "renderProcessSummary(item)" in render_plan
    assert "renderRiskHint(item)" in render_plan
