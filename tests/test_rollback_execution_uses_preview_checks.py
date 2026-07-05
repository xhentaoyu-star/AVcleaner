from __future__ import annotations

from pathlib import Path

from avcleaner.database import connect

from v070_helpers import create_executed_run


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def test_rollback_execution_never_overwrites_and_returns_per_item_code(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    restore_target = tmp_path / "hhd800.com@ABP-123.mp4"
    restore_target.write_bytes(b"new file")

    response = client.post(f"/api/runs/{executed['execute']['run_id']}/rollback", headers=auth_headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["state"] == "rollback_failed"
    assert item["issue_code"] == "restore_target_exists"
    assert item["rollback_error_code"] == "rollback_target_exists"
    assert restore_target.read_bytes() == b"new file"
    assert (tmp_path / "ABP-123.mp4").exists()


def test_rollback_execution_rejects_unknown_item_ids_before_creating_run(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    before = run_count()

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback",
        json={"item_ids": ["missing_item"]},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_run_item"
    assert run_count() == before
