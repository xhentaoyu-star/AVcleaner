from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_execute_button_state_helper_covers_required_blockers() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "function getExecuteButtonState" in text
    for reason in [
        "no_plan",
        "no_selected_items",
        "plan_hash_missing",
        "plan_not_validated",
        "blocking_item_selected",
        "plan_hash_mismatch",
    ]:
        assert reason in text


def test_execute_flow_shows_visible_summary_before_confirmation() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    execute_start = text.index("async function executeSelected")
    summary_pos = text.index("showExecutionSummary()", execute_start)
    visible_confirm_pos = text.index("showExecutionConfirm(summary, selected)", execute_start)

    assert summary_pos < visible_confirm_pos
    assert "window.confirm" not in text[execute_start:text.index("function runMatchesFilter", execute_start)]


def test_confirm_button_is_required_before_execute_api_call() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    assert "executionConfirmPanel" in text
    assert "confirmExecuteSelected" in text
    assert 'bindClick("#confirmExecuteBtn", confirmExecuteSelected)' in text

    confirm_start = text.index("async function confirmExecuteSelected")
    api_pos = text.index('/execute/start`', confirm_start)
    payload_pos = text.index("confirm: true", confirm_start)
    assert api_pos < payload_pos
