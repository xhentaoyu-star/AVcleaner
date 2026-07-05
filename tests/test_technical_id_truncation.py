from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_status_strip_uses_short_ids_with_full_title() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    for marker in ['id="scanId"', 'id="planId"', 'id="planHash"']:
        assert marker in html
    assert "function shortId" in app_js
    assert "node.textContent = shortId(text)" in app_js
    assert "node.title = text" in app_js
    assert 'setCompactText("#scanId"' in app_js
    assert 'setCompactText("#planId"' in app_js
    assert 'setCompactText("#planHash"' in app_js
