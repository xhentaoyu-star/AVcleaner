from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_manual_edit_has_row_level_feedback_and_error_restore() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "async function saveManualEdit" in text
    assert "rowSaving" in text
    assert "previousValue" in text
    assert "nameInput.value = previousValue" in text
    assert "手动修改已保存" in text
    assert "手动修改失败" in text
    assert "is-saving" in text
