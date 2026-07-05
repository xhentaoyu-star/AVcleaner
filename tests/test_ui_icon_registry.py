from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "avcleaner" / "static" / "icons.svg"
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


REQUIRED_ICONS = {
    "folder",
    "analyze",
    "ai",
    "refresh",
    "check",
    "clear",
    "export-json",
    "export-csv",
    "summary",
    "execute",
    "rollback",
    "history",
    "settings",
    "quarantine",
    "details",
    "info",
    "warning",
    "error",
    "blocking",
    "review",
    "edit",
    "copy",
    "diagnostics",
    "success",
    "failed",
    "filter",
    "close",
    "chevron-down",
    "chevron-right",
}


def test_icon_registry_contains_required_symbols() -> None:
    text = ICONS.read_text(encoding="utf-8")

    for icon_name in sorted(REQUIRED_ICONS):
        assert f'id="icon-{icon_name}"' in text


def test_static_icon_buttons_have_accessible_names() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    icon_buttons = re.findall(r"<button\b(?=[^>]*\bicon-btn\b)[^>]*>", html)

    assert icon_buttons
    for button in icon_buttons:
        assert "aria-label=" in button
        assert "title=" in button


def test_frontend_uses_local_icon_sprite() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "/static/icons.svg#icon-" in html
    assert "function icon(" in app_js
    assert "/static/icons.svg#icon-" in app_js
