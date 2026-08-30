from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_custom_junk_extension_is_scanned_and_quarantined(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
) -> None:
    custom_junk = make_file(tmp_path, "unfinished.download", b"partial")
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["rules"]["junk_extensions"] = [*settings["rules"]["junk_extensions"], ".download"]
    saved = client.put("/api/settings", headers=auth_headers, json=settings)
    assert saved.status_code == 200

    scan = client.post(
        "/api/scan",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "recursive": True},
    )

    assert scan.status_code == 200
    scanned = scan.json()
    assert [item["path"] for item in scanned["files"]] == [str(custom_junk)]

    plan = client.post(
        "/api/plans",
        headers=auth_headers,
        json={"scan_id": scanned["scan_id"]},
    )

    assert plan.status_code == 200
    item = plan.json()["items"][0]
    assert item["action"] == "quarantine"
    assert item["reason"] == "download_residue_or_shortcut"
    assert item["selected"] is True


def test_settings_reject_junk_extension_used_by_top_level_media_role(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
) -> None:
    media = make_file(tmp_path, "ABP-123.mp4", b"video")
    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["rules"]["video_extensions"] = [
        extension for extension in settings["rules"]["video_extensions"] if extension != ".mp4"
    ]
    settings["rules"]["junk_extensions"] = [*settings["rules"]["junk_extensions"], ".mp4"]

    saved = client.put("/api/settings", headers=auth_headers, json=settings)

    assert saved.status_code == 422
    assert saved.json()["error_code"] == "rule_settings_extension_role_conflict"

    scan = client.post(
        "/api/scan",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "recursive": True},
    )
    assert scan.status_code == 200
    scanned = scan.json()
    assert [item["path"] for item in scanned["files"]] == [str(media)]

    plan = client.post(
        "/api/plans",
        headers=auth_headers,
        json={"scan_id": scanned["scan_id"]},
    )
    assert plan.status_code == 200
    item = plan.json()["items"][0]
    assert item["action"] != "quarantine"
    assert item["selected"] is False
