from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_toasts_redact_paths_and_secrets() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "function safeToastMessage" in app_js
    assert "SECRET_PATTERNS" in app_js
    assert "toast.textContent = safeToastMessage" in app_js


def test_important_operations_set_loading_or_busy_immediately() -> None:
    app_js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        'setLoading("analyze")',
        'setBusy("validating", true)',
        'setBusy("exporting", true)',
        'setBusy("executing", true)',
        'setBusy("rollingBack", true)',
        'setBusy("loadingDiagnostics", true)',
    ]:
        assert marker in app_js
