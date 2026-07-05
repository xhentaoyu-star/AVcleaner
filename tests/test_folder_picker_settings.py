from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_folder_picker_state_requires_token(client) -> None:
    response = client.get("/api/folder-picker-state")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_folder_picker_last_path_persists(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    response = client.put(
        "/api/folder-picker-state",
        headers=auth_headers,
        json={"last_folder_dialog_dir": str(tmp_path)},
    )

    assert response.status_code == 200
    assert response.json()["last_folder_dialog_dir"] == str(tmp_path)
    loaded = client.get("/api/folder-picker-state", headers=auth_headers)
    assert loaded.json()["last_folder_dialog_dir"] == str(tmp_path)


def test_successful_scan_updates_last_folder_dialog_dir(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "ABP-123.mp4")

    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})

    assert scan.status_code == 200
    state = client.get("/api/folder-picker-state", headers=auth_headers).json()
    assert state["last_folder_dialog_dir"] == str(tmp_path)
