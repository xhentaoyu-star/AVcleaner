from __future__ import annotations

from pathlib import Path

from avcleaner.models import AppSettings
from avcleaner.runtime import runtime_path_info
from avcleaner.settings_store import get_settings, put_settings


def test_first_run_seen_dismissal_does_not_block_workflow(client, auth_headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=auth_headers).json()
    assert settings["first_run_seen"] is False

    settings["first_run_seen"] = True
    saved = client.put("/api/settings", headers=auth_headers, json=settings)

    assert saved.status_code == 200
    assert saved.json()["first_run_seen"] is True
    capabilities = client.get("/api/capabilities")
    assert capabilities.status_code == 200


def test_first_run_seen_persists_with_local_storage_only() -> None:
    saved = put_settings(AppSettings(first_run_seen=True))

    assert saved.first_run_seen is True
    assert get_settings().first_run_seen is True


def test_runtime_modes_have_data_locations_for_first_run_message(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(tmp_path / "dev-data"))
    assert runtime_path_info().mode == "dev"

    monkeypatch.delenv("AVCLEANER_DATA_DIR", raising=False)
    monkeypatch.setenv("AVCLEANER_PORTABLE", "1")
    portable = runtime_path_info(tmp_path / "portable-app")
    assert portable.mode == "portable"
    assert portable.data_dir.name == "data"

    monkeypatch.delenv("AVCLEANER_PORTABLE", raising=False)
    appdata = runtime_path_info(tmp_path / "normal-app")
    assert appdata.mode == "appdata"
