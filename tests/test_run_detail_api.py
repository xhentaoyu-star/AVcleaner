from __future__ import annotations

import json
from pathlib import Path

from avcleaner.database import connect

from v070_helpers import create_executed_run


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def test_run_detail_requires_token(tmp_path: Path, client) -> None:
    response = client.get("/api/runs/run_missing")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_run_detail_returns_safe_structured_fields_and_does_not_mutate(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)
    before = run_count()

    response = client.get(f"/api/runs/{executed['execute']['run_id']}", headers=auth_headers)

    assert response.status_code == 200
    assert run_count() == before
    payload = response.json()
    assert payload["run_id"] == executed["execute"]["run_id"]
    assert payload["plan_id"] == executed["plan"]["plan_id"]
    assert payload["plan_hash"] == executed["plan"]["plan_hash"]
    assert payload["selected_count"] == 1
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["rollback_available"] is True
    item = payload["items"][0]
    for field in [
        "item_id",
        "operation",
        "status",
        "source_name",
        "target_name",
        "source_rel_path",
        "target_rel_path",
        "size",
        "mtime",
        "reason_codes",
        "issue_codes",
        "message_code",
        "message_summary",
        "sidecar_type",
        "media_code",
        "language_suffix",
        "llm_accepted",
        "manual_edited",
        "rollback_status",
        "rollback_error_code",
    ]:
        assert field in item
    assert str(tmp_path) not in json.dumps(payload, ensure_ascii=False)
    assert "Authorization" not in json.dumps(payload)
    assert "api_key" not in json.dumps(payload)


def test_run_detail_missing_run_uses_stable_code(client, auth_headers) -> None:
    response = client.get("/api/runs/run_missing", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_code"] == "run_not_found"
