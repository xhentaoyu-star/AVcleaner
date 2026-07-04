from __future__ import annotations

from pathlib import Path

from avcleaner.models import ScanRequest
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files


def test_plan_api_returns_rule_trace(client, auth_headers: dict[str, str], tmp_path: Path) -> None:
    (tmp_path / "hhd800.com@HEYZO-1234.mp4").write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))

    response = client.post("/api/plans", headers=auth_headers, json={"scan_id": scan.scan_id})

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["trace"]
    assert item["trace"][-1]["after"] == item["suggested_name"]


def test_legacy_execute_remains_disabled_after_trace_changes(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/execute", headers=auth_headers, json={"confirm": True, "items": []})

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"
