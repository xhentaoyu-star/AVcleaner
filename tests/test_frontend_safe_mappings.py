from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_frontend_keeps_stable_codes_but_displays_friendly_labels() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "const ACTION_LABELS" in text
    assert '"rename"' in text
    assert '"quarantine"' in text
    assert "friendlyAction" in text
    assert "friendlyCode" in text
    assert "code:" in text


def test_selection_lock_reasons_have_frontend_mapping() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "const SELECTION_LOCK_EXPLANATIONS" in text
    for reason in ["blocking", "not_executable", "sidecar_default_off"]:
        assert f'"{reason}"' in text


def test_preview_table_keeps_review_data_available() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    for function_name in [
        "renderIssueList",
        "renderTraceList",
        "renderSidecarDetails",
        "renderDetailDrawer",
    ]:
        assert f"function {function_name}" in text

    assert "llm_suggested_name" in text
    assert "llm_reason" in text
    assert "JSON.stringify(item" in text
    assert "cellLlmSuggestion" not in text
