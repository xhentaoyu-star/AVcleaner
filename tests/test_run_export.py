from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from v070_helpers import create_executed_run


EXPECTED_CSV_COLUMNS = [
    "run_id",
    "item_id",
    "operation",
    "status",
    "source_name",
    "target_name",
    "source_rel_path",
    "target_rel_path",
    "media_code",
    "sidecar_type",
    "issue_codes",
    "message_code",
    "rollback_status",
    "rollback_error_code",
    "size",
    "manual_edited",
    "llm_accepted",
]


def test_run_export_requires_token(client) -> None:
    response = client.get("/api/runs/run_missing/export.json")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_run_export_json_has_no_secrets_or_full_paths(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)

    response = client.get(f"/api/runs/{executed['execute']['run_id']}/export.json", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    text = json.dumps(payload, ensure_ascii=False)
    assert payload["run"]["run_id"] == executed["execute"]["run_id"]
    assert payload["summary"]["rollback_available"] is True
    assert "items" in payload
    assert str(tmp_path) not in text
    for forbidden in ["api_key", "Authorization", "Bearer", "raw_payload"]:
        assert forbidden not in text


def test_run_export_csv_columns_are_stable(tmp_path: Path, client, auth_headers) -> None:
    executed = create_executed_run(client, auth_headers, tmp_path)

    response = client.get(f"/api/runs/{executed['execute']['run_id']}/export.csv", headers=auth_headers)

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows
    assert list(rows[0].keys()) == EXPECTED_CSV_COLUMNS
    assert rows[0]["run_id"] == executed["execute"]["run_id"]
