from __future__ import annotations

from avcleaner.models import AppSettings
from avcleaner.settings_store import get_settings, put_settings


def test_first_run_seen_defaults_false() -> None:
    assert get_settings().first_run_seen is False


def test_first_run_seen_persists() -> None:
    saved = put_settings(AppSettings(first_run_seen=True))

    assert saved.first_run_seen is True
    assert get_settings().first_run_seen is True


def test_settings_api_exposes_first_run_seen(client, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/settings", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["first_run_seen"] is False

    payload = response.json()
    payload["first_run_seen"] = True
    saved = client.put("/api/settings", headers=auth_headers, json=payload)

    assert saved.status_code == 200
    assert saved.json()["first_run_seen"] is True
