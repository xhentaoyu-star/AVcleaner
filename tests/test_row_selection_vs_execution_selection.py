from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_row_click_opens_detail_without_toggling_execution_checkbox() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    render_plan = text[text.index("function renderPlan") : text.index("function renderTrash")]

    assert "openDetailDrawer(item.id)" in render_plan
    assert 'checked.addEventListener("click", (event) => event.stopPropagation())' in render_plan
    assert 'updateSelection(checked.checked ? "add" : "remove", [item.id])' in render_plan
    row_click_block = render_plan[render_plan.index('row.addEventListener("click"') : render_plan.index('row.addEventListener("keydown"')]
    assert "updateSelection" not in row_click_block
