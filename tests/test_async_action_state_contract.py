from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_async_actions_have_named_busy_flags() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "busy: {}" in text
    assert "rowSaving: {}" in text
    assert "function setBusy" in text
    assert "function isBusy" in text
    for key in [
        "analyzing",
        "validating",
        "requestingAi",
        "savingEdit",
        "updatingSelection",
        "exporting",
        "executing",
        "rollingBack",
        "loadingHistory",
        "loadingDiagnostics",
    ]:
        assert key in text


def test_analyze_is_guarded_against_duplicate_requests() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert 'isBusy("analyzing")' in text
    assert 'isBusy("requestingAi")' in text
    assert 'setBusy("analyzing", true)' in text
    assert 'setBusy("requestingAi", true)' in text
