from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_focused_detail_row_is_separate_from_execution_selection() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "state.detailItemId === item.id" in text
    assert 'row.setAttribute("aria-selected"' in text
    assert "row.addEventListener(\"click\"" in text
    assert "openDetailDrawer(item.id)" in text
    assert "checked.addEventListener(\"click\", (event) => event.stopPropagation())" in text
    assert 'updateSelection(checked.checked ? "add" : "remove", [item.id])' in text


def test_detail_panel_has_empty_state_without_hiding_panel() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    render_detail = text[text.index("function renderDetailDrawer") : text.index("async function saveManualEdit")]

    assert "panel.hidden = !item" not in render_detail
    assert "未选择项目" in render_detail
    assert 'emptyStateNode("未选择项目"' in render_detail
