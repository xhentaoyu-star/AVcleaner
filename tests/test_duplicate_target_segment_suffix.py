from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_letter_segments_do_not_collapse_into_duplicate_targets(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "FSVSS-004-A.mp4")
    make_file(tmp_path, "FSVSS-004-B.mp4")
    make_file(tmp_path, "FSVSS-004-C.mp4")

    scan = client.post("/api/scan", json={"root_path": str(tmp_path), "recursive": True}, headers=auth_headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=auth_headers)

    assert plan.status_code == 200
    targets = sorted(item["target_name"] for item in plan.json()["items"])
    assert targets == ["FSVSS-004-A.mp4", "FSVSS-004-B.mp4", "FSVSS-004-C.mp4"]
    assert all("duplicate_target" not in item["issue_codes"] for item in plan.json()["items"])
