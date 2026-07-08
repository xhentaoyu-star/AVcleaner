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


def test_execute_rejects_blocking_items_before_creating_run(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "a@ABP-123.mp4")
    make_file(tmp_path, "b@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    before = run_count()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        headers=auth_headers,
        json={"selected_item_ids": [plan["items"][0]["id"]], "confirm": True, "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_item_selected"
    assert run_count() == before


def test_execute_still_requires_explicit_selected_item_ids(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        headers=auth_headers,
        json={"confirm": True, "plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 422


def test_execute_rejects_frontend_settings_override(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        headers=auth_headers,
        json={
            "selected_item_ids": [plan["items"][0]["id"]],
            "confirm": True,
            "plan_hash": plan["plan_hash"],
            "settings_override": {"rename": {"block_extension_change": False}},
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_execute_rejects_frontend_supplied_paths(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        headers=auth_headers,
        json={
            "selected_item_ids": [plan["items"][0]["id"]],
            "confirm": True,
            "plan_hash": plan["plan_hash"],
            "source_path": str(tmp_path / "evil-source.mp4"),
            "target_path": str(tmp_path / "evil-target.mp4"),
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_legacy_execute_remains_disabled_after_review_workflow(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/execute", headers=auth_headers, json={"confirm": True, "items": []})

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"
