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


def test_execute_flow_shows_summary_before_confirmation() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    execute_start = text.index("async function executeSelected")
    summary_pos = text.index("showExecutionSummary()", execute_start)
    confirm_pos = text.index("window.confirm", execute_start)

    assert summary_pos < confirm_pos
