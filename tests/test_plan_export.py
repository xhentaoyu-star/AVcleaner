from __future__ import annotations

import csv
import io
from pathlib import Path

from conftest import make_file

from avcleaner.database import connect


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def table_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def test_plan_json_export_requires_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.get(f"/api/plans/{plan['plan_id']}/export.json")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_plan_json_export_is_non_mutating_and_redacted(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    before = table_counts()

    response = client.get(f"/api/plans/{plan['plan_id']}/export.json", headers=auth_headers)

    assert response.status_code == 200
    assert table_counts() == before
    body = response.json()
    assert body["plan_id"] == plan["plan_id"]
    assert body["plan_hash"] == plan["plan_hash"]
    assert "summary" in body
    assert "items" in body
    serialized = response.text.lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert "source_path" not in body["items"][0]
    assert "target_path" not in body["items"][0]


def test_plan_csv_export_has_practical_columns(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.get(f"/api/plans/{plan['plan_id']}/export.csv", headers=auth_headers)

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows
    assert list(rows[0].keys()) == [
        "item_id",
        "operation",
        "selected",
        "status",
        "original_name",
        "suggested_name",
        "media_code",
        "part_suffix",
        "variant",
        "language_suffix",
        "sidecar_type",
        "group_id",
        "issue_codes",
        "confidence",
        "requires_review",
        "manual_edited",
    ]


def test_plan_csv_export_neutralizes_spreadsheet_formulas(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "=2+2.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.get(f"/api/plans/{plan['plan_id']}/export.csv", headers=auth_headers)

    assert response.status_code == 200
    row = next(csv.DictReader(io.StringIO(response.text)))
    assert row["original_name"] == "'=2+2.mp4"


def test_plan_export_unknown_plan_returns_stable_code(client, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/plans/not-real/export.json", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error_code"] == "plan_not_found"
