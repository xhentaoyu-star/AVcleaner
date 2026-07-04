from __future__ import annotations

from pathlib import Path

from conftest import make_file


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def test_plan_summary_exposes_review_bucket_counts(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.zh.srt")

    plan = create_plan(client, auth_headers, tmp_path)
    summary = plan["summary"]

    assert summary["total_items"] == 3
    assert summary["rename_items"] >= 1
    assert summary["sidecar_items"] == 1
    assert summary["requires_review_items"] >= 1
    assert "safe_selectable_items" in summary


def test_plan_items_expose_review_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")

    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    assert item["blocking"] is False
    assert item["warning_count"] == 0
    assert item["issue_codes"] == []
    assert item["requires_review"] is True
    assert "requires_review" in item["review_buckets"]
    assert item["selected"] is False


def test_duplicate_plan_items_are_in_conflict_bucket(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "a@ABP-123.mp4")
    make_file(tmp_path, "b@ABP-123.mp4")

    plan = create_plan(client, auth_headers, tmp_path)

    assert plan["summary"]["conflict_items"] == 2
    assert all("conflict" in item["review_buckets"] for item in plan["items"])
    assert all(item["blocking"] is True for item in plan["items"])


def test_sidecar_default_selection_fields_are_stable(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    make_file(tmp_path, "hhd800.com@ABP-123.zh.srt")

    plan = create_plan(client, auth_headers, tmp_path)
    sidecar = next(item for item in plan["items"] if item["sidecar_type"] == "subtitle")

    assert sidecar["selected"] is False
    assert sidecar["selected_default"] is False
    assert sidecar["selection_reason"] == "sidecar_default_off"
    assert "sidecar" in sidecar["review_buckets"]
