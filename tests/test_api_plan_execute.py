from __future__ import annotations

from pathlib import Path

from conftest import make_file


def create_scan_and_plan(client, headers, root: Path):
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return scan.json(), plan.json()


def test_api_scan_plan_execute_and_runs(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, tmp_path)

    selected = [item["id"] for item in plan["items"] if item["checked"]]
    execute = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json={"selected_item_ids": selected, "confirm": True, "plan_hash": plan["plan_hash"]},
        headers=auth_headers,
    )

    assert execute.status_code == 200
    assert (tmp_path / "ABP-123.mp4").exists()
    runs = client.get("/api/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert runs.json()


def test_legacy_execute_is_disabled(tmp_path: Path, client, auth_headers) -> None:
    response = client.post("/api/execute", json={"confirm": True, "items": []}, headers=auth_headers)

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"


def test_execute_requires_matching_plan_hash(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, tmp_path)
    selected = [item["id"] for item in plan["items"] if item["checked"]]

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json={"selected_item_ids": selected, "confirm": True, "plan_hash": "bad"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "plan_hash_mismatch"


def test_execute_rejects_extra_frontend_fields(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json={
            "selected_item_ids": [plan["items"][0]["id"]],
            "confirm": True,
            "plan_hash": plan["plan_hash"],
            "items": [{"source_path": "C:\\Users\\bad", "target_path": "L:\\bad.mp4"}],
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_get_plan_returns_persisted_plan(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, tmp_path)

    response = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["plan_hash"] == plan["plan_hash"]


def test_patch_plan_item_rehashes_and_revalidates(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, tmp_path)
    item_id = plan["items"][0]["id"]

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item_id}",
        json={"target_name": "ABP-123-C.mp4"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["plan_hash"] != plan["plan_hash"]
    assert response.json()["item"]["target_name"] == "ABP-123-C.mp4"
