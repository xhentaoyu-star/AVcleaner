from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_sidecar_rename_suggestions_are_not_selected_by_default(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "ABP-123.mp4")
    make_file(tmp_path, "[ad] ABP123.zh.srt")

    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})
    plan = client.post("/api/plans", headers=auth_headers, json={"scan_id": scan.json()["scan_id"]})

    assert plan.status_code == 200
    subtitle = next(item for item in plan.json()["items"] if item["original_name"] == "[ad] ABP123.zh.srt")
    selected = [item["id"] for item in plan.json()["items"] if item["checked"]]

    assert subtitle["action"] == "rename"
    assert subtitle["target_name"] == "ABP-123.zh.srt"
    assert subtitle["checked"] is False
    assert subtitle["selected_default"] is False
    assert subtitle["id"] not in selected


def test_default_execute_does_not_rename_sidecar_suggestions(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "[ad] ABP123.zh.srt")

    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})
    plan = client.post("/api/plans", headers=auth_headers, json={"scan_id": scan.json()["scan_id"]})
    body = plan.json()
    selected = [item["id"] for item in body["items"] if item["checked"]]

    response = client.post(
        f"/api/plans/{body['plan_id']}/execute",
        headers=auth_headers,
        json={"selected_item_ids": selected, "confirm": True, "plan_hash": body["plan_hash"]},
    )

    assert response.status_code == 200
    assert (tmp_path / "ABP-123.mp4").exists()
    assert (tmp_path / "[ad] ABP123.zh.srt").exists()
    assert not (tmp_path / "ABP-123.zh.srt").exists()
