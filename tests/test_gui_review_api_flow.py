from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_review_api_flow_select_edit_summarize_and_export(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.zh.srt")

    scan = client.post("/api/scan", json={"root_path": str(tmp_path), "recursive": True}, headers=auth_headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=auth_headers).json()

    selection = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"mode": "select_safe", "selected_item_ids": []},
    )
    assert selection.status_code == 200
    selected_ids = selection.json()["selected_item_ids"]
    assert selected_ids
    assert all(
        not item["sidecar_type"]
        for item in selection.json()["items"]
        if item["id"] in selected_ids
    )

    editable = next(item for item in selection.json()["items"] if item["id"] in selected_ids)
    edit = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{editable['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123-C.mp4"},
    )
    assert edit.status_code == 200

    summary = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": [editable["id"]], "plan_hash": edit.json()["plan_hash"]},
    )
    assert summary.status_code == 200
    assert summary.json()["selected_count"] == 1

    exported = client.get(f"/api/plans/{plan['plan_id']}/export.json", headers=auth_headers)
    assert exported.status_code == 200
    exported_item = next(item for item in exported.json()["items"] if item["item_id"] == editable["id"])
    assert exported_item["manual_edited"] is True
    assert exported_item["suggested_name"] == "ABP-123-C.mp4"
