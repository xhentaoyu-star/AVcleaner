from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_detail_panel_has_simple_sections_and_debug_appendix() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        'detailSection("文件"',
        'detailSection("最终文件名"',
        'detailSection("处理"',
        'detailSection("风险/提示"',
        'detailSection("路径"',
    ]:
        assert marker in app_js
    assert 'detailSection("AI 建议"' in app_js
    assert 'detailSection("Debug' in app_js


def test_unselected_detail_panel_is_small_empty_state() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'body.append(emptyStateNode("选择左侧文件查看详情"' in app_js
    assert 'panel.classList.toggle("is-empty", !item)' in app_js
