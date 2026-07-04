from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import PlanRequest, RuleSettings, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files


def persisted_scan(root: Path):
    scan = scan_files(ScanRequest(root_path=str(root)))
    return create_scan(ScanRequest(root_path=str(root)), scan)


def test_relevant_rule_settings_change_plan_hash(tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    make_file(root, "ABP-123_2-C.mp4")
    scan = persisted_scan(root)

    default_plan = create_plan(PlanRequest(scan_id=scan.scan_id, rules=RuleSettings()))
    changed_plan = create_plan(
        PlanRequest(scan_id=scan.scan_id, rules=RuleSettings(output_template="{code}{variant}{part}{language}{ext}"))
    )

    assert default_plan.plan_hash != changed_plan.plan_hash
    assert default_plan.items[0].target_name == "ABP-123-2-C.mp4"
    assert changed_plan.items[0].target_name == "ABP-123-C-2.mp4"


def test_plan_hash_includes_ruleset_hash_even_when_target_name_matches(tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    make_file(root, "customads.invalid@ABP-123.mp4")
    scan = persisted_scan(root)

    default_plan = create_plan(PlanRequest(scan_id=scan.scan_id, rules=RuleSettings()))
    custom_plan = create_plan(PlanRequest(scan_id=scan.scan_id, rules=RuleSettings(remove_ad_domains=["customads.invalid"])))

    assert default_plan.plan_hash != custom_plan.plan_hash
    assert default_plan.items[0].ruleset_hash != custom_plan.items[0].ruleset_hash


def test_api_create_plan_uses_persisted_settings_not_frontend_rules(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "ABP-123_2-C.mp4")
    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})

    response = client.post(
        "/api/plans",
        headers=auth_headers,
        json={
            "scan_id": scan.json()["scan_id"],
            "rules": {"output_template": "{code}{variant}{part}{language}{ext}"},
        },
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["target_name"] == "ABP-123-2-C.mp4"


def test_execute_endpoint_rejects_settings_override_fields(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = client.post("/api/scan", headers=auth_headers, json={"root_path": str(tmp_path), "recursive": True})
    plan = client.post("/api/plans", headers=auth_headers, json={"scan_id": scan.json()["scan_id"]}).json()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/execute",
        headers=auth_headers,
        json={
            "selected_item_ids": [item["id"] for item in plan["items"] if item["checked"]],
            "confirm": True,
            "plan_hash": plan["plan_hash"],
            "rules": {"output_template": "{code}{variant}{part}{language}{ext}"},
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"
