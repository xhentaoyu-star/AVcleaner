from __future__ import annotations

from pathlib import Path

from v070_helpers import make_file


def test_recent_folder_added_after_scan(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    scan = client.post("/api/scan", json={"root_path": str(tmp_path), "recursive": True}, headers=auth_headers)
    recent = client.get("/api/recent-folders", headers=auth_headers)

    assert scan.status_code == 200
    assert recent.status_code == 200
    assert recent.json()[0]["path"] == str(tmp_path)
    assert recent.json()[0]["last_scan_id"] == scan.json()["scan_id"]
    assert recent.json()[0]["item_count"] == 1


def test_recent_folders_require_token(client) -> None:
    response = client.get("/api/recent-folders")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_recent_folder_dedupe_limit_and_clear(tmp_path: Path, client, auth_headers) -> None:
    first = tmp_path / "Folder"
    client.post("/api/recent-folders", json={"path": str(first), "item_count": 1}, headers=auth_headers)
    client.post("/api/recent-folders", json={"path": str(first).upper(), "item_count": 2}, headers=auth_headers)
    deduped = client.get("/api/recent-folders", headers=auth_headers).json()
    assert len(deduped) == 1
    assert deduped[0]["item_count"] == 2

    for index in range(12):
        client.post(
            "/api/recent-folders",
            json={"path": str(tmp_path / f"folder-{index}"), "item_count": index},
            headers=auth_headers,
        )

    recent = client.get("/api/recent-folders", headers=auth_headers)
    assert recent.status_code == 200
    assert len(recent.json()) == 10

    clear = client.delete("/api/recent-folders", headers=auth_headers)
    assert clear.status_code == 200
    assert client.get("/api/recent-folders", headers=auth_headers).json() == []
