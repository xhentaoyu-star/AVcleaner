from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
CSS = ROOT / "avcleaner" / "static" / "styles.css"
JS = ROOT / "avcleaner" / "static" / "app.js"


def test_sidebar_shell_replaces_top_navigation() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'class="app-layout"' in html
    assert 'class="sidebar"' in html
    assert 'class="sidebar-header"' in html
    assert 'class="sidebar-nav"' in html
    assert 'class="sidebar-footer"' in html
    assert "content-shell" in html
    assert 'class="content-column"' in html
    assert 'class="nav-tabs"' not in html
    assert 'data-zone="topbar"' not in html


def test_sidebar_keeps_existing_tab_contract() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    for tab in ["workspace", "trash", "history", "settings"]:
        assert f'data-tab="{tab}"' in html
        assert f'data-panel="{tab}"' in html
    assert ".sidebar-nav button[data-tab]" in js
    assert ".nav-tabs button[data-tab]" not in js


def test_sidebar_contains_user_tools_without_visible_debug_toggle() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert 'id="globalSearch"' in html
    assert 'id="topFolderPickerBtn"' in html
    assert 'id="debugModeToggle"' not in html
    assert "data-ui-detail-toggle" not in html
    assert 'data-sidebar-tool="notice"' in html
    assert 'data-sidebar-tool="help"' in html


def test_centered_card_workbench_css_contract() -> None:
    css = CSS.read_text(encoding="utf-8")
    sidebar_css = css[css.index("/* v0.8.0 OpenAver-style sidebar shell */") :]

    assert ".app-layout" in sidebar_css
    assert "grid-template-columns: 244px minmax(0, 1fr)" in sidebar_css
    assert ".content-column" in sidebar_css
    assert "max-width: 1080px" in sidebar_css
    assert ".review-workbench" in sidebar_css
    assert "grid-template-columns: 1fr" in sidebar_css
    assert "@media (max-width: 1279px)" in sidebar_css


def test_sidebar_layout_capability_flags(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["capabilities"]["sidebar_layout"] is True
    assert body["capabilities"]["opena_ver_inspired_shell"] is True
    assert body["capabilities"]["centered_card_workbench"] is True
