from __future__ import annotations

from pathlib import Path

from avcleaner.database import connect

from v070_helpers import create_executed_run


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def test_rollback_preview_requires_token(client) -> None:
    response = client.post("/api/runs/run_missing/rollback-preview", json={"item_ids": None})

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_rollback_preview_is_non_mutating_and_reports_safe_action(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    before = run_count()

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback-preview",
        json={"item_ids": None},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert run_count() == before
    payload = response.json()
    assert payload["ok_to_rollback"] is True
    assert payload["summary"]["rollbackable_items"] == 1
    assert payload["items"][0]["rollback_action"] == "rename_back"
    assert payload["items"][0]["current_path_status"] == "available"
    assert payload["items"][0]["restore_target_status"] == "free"
    assert (tmp_path / "ABP-123.mp4").exists()
    assert not (tmp_path / "hhd800.com@ABP-123.mp4").exists()


def test_rollback_preview_rejects_unknown_item_ids(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/runs/{executed['execute']['run_id']}/rollback-preview",
        json={"item_ids": ["missing_item"]},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_run_item"
