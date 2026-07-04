from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.database import connect


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def test_execution_summary_requires_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        json={"selected_item_ids": [plan["items"][0]["id"]], "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_execution_summary_is_non_mutating(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    selected = [item["id"] for item in plan["items"] if item["selected"]]
    before = run_count()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": selected, "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok_to_execute"] is True
    assert body["selected_count"] == len(selected)
    assert body["rename_count"] == len(selected)
    assert run_count() == before


def test_execution_summary_rejects_hash_mismatch(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": [plan["items"][0]["id"]], "plan_hash": "bad"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "plan_hash_mismatch"


def test_execution_summary_rejects_unknown_item(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": ["not-real"], "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_plan_item"


def test_execution_summary_flags_blocking_items(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "a@ABP-123.mp4")
    make_file(tmp_path, "b@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": [plan["items"][0]["id"]], "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok_to_execute"] is False
    assert body["blocking_count"] == 1
    assert "blocking_item_selected" in body["messages"]


def test_execution_summary_rejects_extra_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execution-summary",
        headers=auth_headers,
        json={"selected_item_ids": [plan["items"][0]["id"]], "plan_hash": plan["plan_hash"], "target_path": "C:\\bad.mp4"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"
