from __future__ import annotations


def test_settings_api_round_trips_quarantine_directory(client, auth_headers: dict[str, str], tmp_path) -> None:
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["quarantine_dir"] = str(tmp_path / "quarantine-outside-source")

    response = client.put("/api/settings", headers=auth_headers, json=settings)

    assert response.status_code == 200
    assert response.json()["quarantine_dir"] == str(tmp_path / "quarantine-outside-source")


def test_settings_rejects_invalid_quarantine_directory(client, auth_headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["quarantine_dir"] = "bad\x00path"

    response = client.put("/api/settings", headers=auth_headers, json=settings)

    assert response.status_code == 422
    assert response.json()["error_code"] == "settings_invalid_quarantine_dir"
