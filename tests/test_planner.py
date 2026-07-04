from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.enums import IssueCode, Operation
from avcleaner.models import PlanRequest, ScanRequest
from avcleaner.planner import create_plan, patch_plan_item, validate_stored_plan
from avcleaner.repository import create_scan, get_plan
from avcleaner.scanner import scan_files


def persisted_scan(root: Path):
    response = scan_files(ScanRequest(root_path=str(root)))
    return create_scan(ScanRequest(root_path=str(root)), response)


def test_create_plan_from_scan_id_persists_items(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = persisted_scan(tmp_path)

    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    stored = get_plan(plan.plan_id)

    assert stored.plan_id == plan.plan_id
    assert stored.items[0].target_name == "ABP-123.mp4"


def test_plan_hash_is_stable_for_stored_plan(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = persisted_scan(tmp_path)
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert get_plan(plan.plan_id).plan_hash == plan.plan_hash


def test_manual_patch_changes_hash(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = persisted_scan(tmp_path)
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    patched = patch_plan_item(plan.plan_id, plan.items[0].id, "ABP-123-C.mp4")

    assert patched.plan_hash != plan.plan_hash
    assert patched.item.source == "manual"


def test_duplicate_targets_are_blocked_not_cd_suffixed(tmp_path: Path) -> None:
    make_file(tmp_path, "a@ABP-123.mp4")
    make_file(tmp_path, "b@ABP-123.mp4")
    scan = persisted_scan(tmp_path)

    plan = create_plan(PlanRequest(scan_id=scan.scan_id))
    names = {item.target_name for item in plan.items}

    assert names == {"ABP-123.mp4"}
    assert all(any(issue.code == IssueCode.DUPLICATE_TARGET for issue in item.issues) for item in plan.items)


def test_junk_file_becomes_quarantine_plan_item(tmp_path: Path) -> None:
    make_file(tmp_path, "ad.url", b"[InternetShortcut]")
    scan = persisted_scan(tmp_path)

    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert plan.items[0].action == Operation.QUARANTINE
    assert plan.items[0].checked


def test_media_without_code_requires_review(tmp_path: Path) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    scan = persisted_scan(tmp_path)

    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert plan.items[0].action == Operation.REVIEW
    assert plan.items[0].requires_review


def test_validate_stored_plan_refreshes_hash(tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = persisted_scan(tmp_path)
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    validated = validate_stored_plan(plan.plan_id)

    assert validated.plan_id == plan.plan_id
    assert validated.plan_hash == get_plan(plan.plan_id).plan_hash
