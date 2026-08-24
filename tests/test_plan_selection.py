from __future__ import annotations

from pathlib import Path

from conftest import make_file


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def test_selection_api_requires_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        json={"selected_item_ids": [], "mode": "replace"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_selection_api_rejects_wrong_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers={"X-AVCleaner-Token": "wrong"},
        json={"selected_item_ids": [], "mode": "replace"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "api_token_invalid"


def test_selection_api_rejects_unknown_items(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"selected_item_ids": ["not-real"], "mode": "replace"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_plan_item"


def test_selection_api_rejects_extra_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"selected_item_ids": [], "mode": "replace", "source_path": "C:\\bad.mp4"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_selection_api_rejects_blocking_items(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "a@ABP-123.mp4")
    make_file(tmp_path, "b@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"selected_item_ids": [plan["items"][0]["id"]], "mode": "replace"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_item_selected"


def test_selection_api_rejects_requires_review_quarantine_items(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    residue = tmp_path / "midv-192-4k.mp4.xltd"
    with residue.open("wb") as handle:
        handle.truncate(2 * 1024 * 1024 * 1024)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    assert item["requires_review"] is True
    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"selected_item_ids": [item["id"]], "mode": "replace"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_item_selected"


def test_select_safe_persists_only_nonblocking_nonreview_non_sidecars(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.zh.srt")
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"mode": "select_safe", "selected_item_ids": []},
    )

    assert response.status_code == 200
    body = response.json()
    selected = body["selected_item_ids"]
    assert selected
    selected_items = [item for item in body["items"] if item["id"] in selected]
    assert all(not item["blocking"] for item in selected_items)
    assert all(not item["requires_review"] for item in selected_items)
    assert all(not item["sidecar_type"] for item in selected_items)
    stored = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()
    assert {item["id"] for item in stored["items"] if item["selected"]} == set(selected)


def test_sidecar_can_only_be_selected_explicitly_when_nonblocking(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.zh.srt")
    plan = create_plan(client, auth_headers, tmp_path)
    sidecar = next(item for item in plan["items"] if item["sidecar_type"] == "subtitle")

    assert sidecar["selected"] is False
    response = client.patch(
        f"/api/plans/{plan['plan_id']}/selection",
        headers=auth_headers,
        json={"mode": "replace", "selected_item_ids": [sidecar["id"]]},
    )

    assert response.status_code == 200
    stored_sidecar = next(item for item in response.json()["items"] if item["id"] == sidecar["id"])
    assert stored_sidecar["selected"] is True
