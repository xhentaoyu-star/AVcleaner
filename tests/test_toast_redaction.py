from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js"


def test_toast_feedback_redacts_sensitive_patterns() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "function sanitizeFeedbackMessage" in text
    for marker in [
        "Authorization",
        "X-AVCleaner-Token",
        "api[_-]?key",
        "sk-",
        "[路径已隐藏]",
        "[已隐藏]",
    ]:
        assert marker in text


def test_toast_uses_sanitized_text_only() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "node.textContent = text" in text
    assert "sanitizeFeedbackMessage(friendlyMessage(message))" in text
