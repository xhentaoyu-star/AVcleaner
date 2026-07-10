from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_right_detail_stack_is_sticky_and_scrolls_internally() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert 'class="detail-panel detail-drawer detail-stack"' in html
    assert ".detail-stack" in css
    assert "position: sticky" in css
    assert "max-height: calc(100vh - 96px)" in css
    assert ".detail-stack .drawer-body" in css
    assert "overflow: auto" in css


def test_detail_panel_carries_full_context_not_table() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    render_detail = text[text.index("function renderDetailDrawer") : text.index("async function saveManualEdit")]

    for label in ["文件", "最终文件名", "处理", "风险/提示", "AI 建议", "Debug 信息", "快捷操作"]:
        assert label in render_detail
    assert "完整路径" in render_detail
    assert "source_path" in text[text.index("function debugDetailsNode") : text.index("function groupLabel")]
    assert 'summary.textContent = "Debug 信息"' in text
    assert "选择左侧文件查看详情" in render_detail
