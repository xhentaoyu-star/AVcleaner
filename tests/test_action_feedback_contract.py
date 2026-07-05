from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_action_feedback_uses_busy_state_and_toast_helpers() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "function setBusy",
        "function busyAny",
        "function showFeedback",
        "function toast",
        "function setStatus",
        "sanitizeFeedbackMessage",
    ]:
        assert marker in text


def test_feedback_redacts_sensitive_values() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    for marker in [
        "Authorization",
        "X-AVCleaner-Token",
        "api[_-]?key",
        "Bearer",
        "sk-",
    ]:
        assert marker in text
