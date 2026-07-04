from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_plan_api_exposes_sidecar_group_metadata(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "[ad] ABP123.zh-CN.srt")
    make_file(tmp_path, "ABP-123.webp")

    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})
    assert scan.status_code == 200
    plan = client.post("/api/plans", headers=auth_headers, json={"scan_id": scan.json()["scan_id"]})

    assert plan.status_code == 200
    items = {item["original_name"]: item for item in plan.json()["items"]}
    video = items["hhd800.com@ABP-123.mp4"]
    subtitle = items["[ad] ABP123.zh-CN.srt"]
    image = items["ABP-123.webp"]

    assert subtitle["group_id"] == video["group_id"]
    assert image["group_id"] == video["group_id"]
    assert subtitle["sidecar_type"] == "subtitle"
    assert subtitle["language_suffix"] == "zh-CN"
    assert subtitle["associated_media_code"] == "ABP-123"
    assert subtitle["checked"] is False
    assert subtitle["selected_default"] is False
    assert subtitle["trace"]
    assert image["sidecar_type"] == "image"
    assert image["checked"] is False


def test_sidecar_grouping_does_not_weaken_legacy_execute_guard(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/execute", headers=auth_headers, json={"confirm": True, "items": []})

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"
