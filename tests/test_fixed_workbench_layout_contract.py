from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
CSS = ROOT / "avcleaner" / "static" / "styles.css"


def test_workbench_uses_responsive_v084_baseline() -> None:
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    v084_css = css[css.index("/* V0.8.4 product workspace shell */") :]

    assert 'data-workbench-version="0.8.4"' in html
    assert "--content-max: 1660px" in css
    assert "min-width: 1280px" not in v084_css
    assert "@media (max-width: 1180px)" in v084_css
    assert "@media (max-width: 820px)" in v084_css
    assert "@media (max-width: 560px)" in v084_css
    assert "@media (prefers-reduced-motion: reduce)" in v084_css


def test_capabilities_expose_workbench_redesign_flags(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.8.4"
    assert body["desktop_window"] == {
        "default_width": 1440,
        "default_height": 900,
        "minimum_width": 960,
        "minimum_height": 700,
        "recommended_width": 1440,
        "recommended_height": 900,
        "content_max_width": 1660,
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
