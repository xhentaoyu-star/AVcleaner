from __future__ import annotations

from pathlib import Path

from conftest import make_file


def create_plan(client, headers, root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def execute_payload(plan: dict, **overrides) -> dict:
    payload = {
        "selected_item_ids": [item["id"] for item in plan["items"] if item["checked"]],
        "confirm": True,
        "plan_hash": plan["plan_hash"],
    }
    payload.update(overrides)
    return payload


def test_execute_missing_token_is_blocked(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(f"/api/plans/{plan['plan_id']}/execute", json=execute_payload(plan))

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_execute_wrong_token_is_blocked(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(plan),
        headers={"X-AVCleaner-Token": "wrong"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "api_token_invalid"


def test_execute_missing_confirm_is_rejected(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    payload = execute_payload(plan)
    payload.pop("confirm")

    response = client.post(f"/api/plans/{plan['plan_id']}/execute", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["error_code"] == "confirm_required"


def test_execute_confirm_false_is_rejected(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(plan, confirm=False),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "confirm_required"


def test_execute_missing_plan_hash_is_rejected(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    payload = execute_payload(plan)
    payload.pop("plan_hash")

    response = client.post(f"/api/plans/{plan['plan_id']}/execute", json=payload, headers=auth_headers)

    assert response.status_code == 422


def test_execute_mismatched_plan_hash_is_rejected(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(plan, plan_hash="bad"),
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "plan_hash_mismatch"


def test_execute_unknown_selected_item_ids_are_rejected_before_run(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(plan, selected_item_ids=["not-real"]),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_selected_item_ids"


def test_execute_extra_frontend_file_operation_fields_are_rejected(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(
            plan,
            source_path="C:\\Users\\forged.mp4",
            target_path="L:\\forged.mp4",
        ),
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_execute_ignores_client_attempt_to_change_plan_item_path(tmp_path: Path, client, auth_headers) -> None:
    source = make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    forged_target = tmp_path / "FORGED.mp4"
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        json=execute_payload(plan),
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert not source.exists()
    assert (tmp_path / "ABP-123.mp4").exists()
    assert not forged_target.exists()
