from __future__ import annotations

import os
from pathlib import Path

from v070_helpers import create_executed_run


def test_rollback_preview_detects_restore_target_conflict(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    (tmp_path / "hhd800.com@ABP-123.mp4").write_bytes(b"new file")

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback-preview",
        json={"item_ids": None},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok_to_rollback"] is False
    assert payload["summary"]["conflict_items"] == 1
    assert payload["items"][0]["restore_target_status"] == "exists"
    assert "rollback_target_exists" in payload["items"][0]["issue_codes"]


def test_rollback_preview_reports_already_completed(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    rollback = client.post(f"/api/runs/{executed['execute']['run_id']}/rollback", headers=auth_headers)
    assert rollback.status_code == 200

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback-preview",
        json={"item_ids": None},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "rollback_already_completed"


def test_rollback_preview_detects_same_size_same_mtime_content_change(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    renamed = tmp_path / "ABP-123.mp4"
    original_stat = renamed.stat()
    renamed.write_bytes(b"other")
    os.utime(renamed, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback-preview",
        json={"item_ids": None},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok_to_rollback"] is False
    assert payload["items"][0]["current_path_status"] == "changed"
    assert "rollback_file_changed" in payload["items"][0]["issue_codes"]
