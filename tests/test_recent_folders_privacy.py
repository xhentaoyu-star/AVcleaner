from __future__ import annotations

import json
from pathlib import Path

from v070_helpers import create_scan_and_plan, make_file


def test_recent_folders_not_in_settings_export_by_default(tmp_path: Path, client, auth_headers) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    scan = client.post("/api/scan", json={"root_path": str(tmp_path), "recursive": True}, headers=auth_headers)
    assert scan.status_code == 200

    exported = client.get("/api/settings/export", headers=auth_headers)

    assert exported.status_code == 200
    text = json.dumps(exported.json(), ensure_ascii=False)
    assert "recent_folders" not in text
    assert str(tmp_path) not in text


def test_recent_folders_not_sent_to_llm_payloads(tmp_path: Path, client, auth_headers) -> None:
    recent_path = tmp_path / "recent-private-root"
    make_file(recent_path, "hhd800.com@ABP-123.mp4")
    _scan, plan = create_scan_and_plan(client, auth_headers, recent_path)
    item_ids = [item["id"] for item in plan["items"][:1]]

    payload = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        json={"item_ids": item_ids, "include_neighbors": True},
        headers=auth_headers,
    )

    assert payload.status_code == 200
    text = json.dumps(payload.json(), ensure_ascii=False)
    assert str(recent_path) not in text
    assert "recent_folders" not in text
