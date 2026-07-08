from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"
LOGO = ROOT / "avcleaner" / "static" / "logo-icon.png"


def test_local_logo_icon_is_used_in_header_and_favicon() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert LOGO.exists()
    assert LOGO.stat().st_size > 0
    assert '<link rel="icon" type="image/png" href="/static/logo-icon.png" />' in html
    assert '<img src="/static/logo-icon.png" alt="" />' in html


def test_workspace_has_compact_safety_banner() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'class="safety-banner"' in html
    assert "安全预览" in html
    assert "扫描和预览不会修改文件" in html
    assert 'data-debug-only data-debug-field="legacy-endpoint-status"' in html
