from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_execution_module_is_compact_and_summary_first() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'class="execution-module"' in html
    for marker in ["executionPillRename", "executionPillQuarantine", "executionPillSkip", "executionPillWarning"]:
        assert f'id="{marker}"' in html
    assert 'id="executionSummaryBtn"' in html
    assert 'id="executeBtn"' in html
    assert 'id="confirmExecuteBtn"' in html
    assert 'id="executionProgressPanel"' in html
    assert 'id="executionOverallProgressBar"' in html
    assert 'id="executionFileProgressBar"' in html
    assert 'class="run-result-grid"' in html


def test_execute_api_call_still_uses_authoritative_payload_only() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    confirm_start = text.index("async function confirmExecuteSelected")
    confirm_block = text[confirm_start:text.index("function runMatchesFilter", confirm_start)]

    assert "/execute/start`" in confirm_block
    assert "/progress`" in text
    assert "selected_item_ids: selectedIds" in confirm_block
    assert "confirm: true" in confirm_block
    assert "plan_hash: state.plan.plan_hash" in confirm_block
    assert "source_path" not in confirm_block
    assert "target_path" not in confirm_block


def test_execute_success_does_not_auto_rerun_analyze() -> None:
    text = APP_JS.read_text(encoding="utf-8")
    confirm_start = text.index("async function confirmExecuteSelected")
    confirm_block = text[confirm_start:text.index("function runMatchesFilter", confirm_start)]

    assert "await refreshRuns();" in confirm_block
    assert "await analyze();" not in confirm_block
    assert 'state.plan.state = "executed"' in confirm_block
