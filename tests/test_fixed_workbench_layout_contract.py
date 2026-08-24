from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_fixed_workbench_uses_desktop_baseline() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    v075_css = css[css.index("/* v0.7.5 fixed desktop workbench */") :]

    assert 'data-workbench-version="0.8.2"' in html
    assert "min-width: 1280px" in v075_css
    assert "1480px" in v075_css
    assert "overflow-x: auto" in v075_css
    assert "grid-template-columns: minmax(760px, 1fr) 380px" in v075_css
    assert "calc(100vh - 470px)" in v075_css


def test_capabilities_expose_workbench_redesign_flags(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.8.2"
    assert body["desktop_window"] == {
        "default_width": 1440,
        "default_height": 900,
        "minimum_width": 1280,
        "minimum_height": 760,
        "recommended_width": 1440,
        "recommended_height": 900,
        "content_max_width": 1080,
    }
    for flag in [
        "fixed_workbench_layout",
        "desktop_window_baseline",
        "right_detail_stack",
        "compact_execution_module",
        "workbench_visual_redesign",
        "simple_ui_mode",
        "debug_ui_mode",
        "progressive_disclosure",
        "sidebar_layout",
        "opena_ver_inspired_shell",
        "centered_card_workbench",
    ]:
        assert body["capabilities"][flag] is True
