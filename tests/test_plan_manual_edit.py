from __future__ import annotations

from pathlib import Path

from conftest import make_file


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def test_manual_edit_accepts_only_target_name(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{plan['items'][0]['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123-C.mp4", "source_path": "C:\\forged.mp4"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_manual_edit_rejects_path_separator(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{plan['items'][0]['id']}",
        headers=auth_headers,
        json={"target_name": "nested\\ABP-123.mp4"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "path_separator_in_target"


def test_manual_edit_rejects_empty_name(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{plan['items'][0]['id']}",
        headers=auth_headers,
        json={"target_name": "   "},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_target_name"


def test_manual_edit_rejects_extension_change(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{plan['items'][0]['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123.mkv"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "extension_changed"


def test_manual_edit_updates_hash_and_review_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{plan['items'][0]['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123-C.mp4"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_hash"] != plan["plan_hash"]
    assert body["item"]["manual_edited"] is True
    assert body["item"]["last_edited_at"]
    assert "manual_edited" in body["item"]["review_buckets"]
    assert body["item"]["trace"][-1]["rule_id"] == "manual_edit"


def test_manual_edit_revalidates_duplicate_conflicts(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "hhd800.com@ABP-124.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    item = next(row for row in plan["items"] if row["target_name"] == "ABP-124.mp4")

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123.mp4"},
    )

    assert response.status_code == 200
    affected = response.json()["affected_items"]
    conflict_items = [row for row in affected if "conflict" in row["review_buckets"]]
    assert conflict_items
    assert all("duplicate_target" in row["issue_codes"] for row in conflict_items)


def test_manual_edit_unknown_item_returns_stable_code(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/not-real",
        headers=auth_headers,
        json={"target_name": "ABP-123-C.mp4"},
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "unknown_plan_item"
