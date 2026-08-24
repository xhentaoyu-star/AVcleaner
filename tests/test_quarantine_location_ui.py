from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_quarantine_page_exposes_current_location_and_native_picker() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        'id="quarantineLocation"',
        'id="quarantineLocationStatus"',
        'id="quarantineFolderPickerBtn"',
        'id="resetQuarantineFolderBtn"',
    ]:
        assert marker in html

    for marker in [
        "function renderQuarantineLocation",
        "async function loadQuarantineLocation",
        "async function chooseQuarantineFolder",
        "async function resetQuarantineFolder",
        'bindClick("#quarantineFolderPickerBtn", chooseQuarantineFolder)',
        'bindClick("#resetQuarantineFolderBtn", resetQuarantineFolder)',
        "const alreadyDefault = Boolean(state.quarantineLocation?.using_default",
        "resetQuarantineFolderBtn.disabled = isBusyNow || !state.settings || alreadyDefault",
    ]:
        assert marker in app_js


def test_quarantine_location_api_reports_effective_selected_directory(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    selected = tmp_path / "selected-quarantine"
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["quarantine_dir"] = str(selected)
    saved = client.put("/api/settings", headers=auth_headers, json=settings)
    assert saved.status_code == 200

    response = client.get("/api/quarantine/location", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "configured_dir": str(selected),
        "effective_dir": str(selected),
        "using_default": False,
        "fallback_active": False,
        "writable": True,
    }
