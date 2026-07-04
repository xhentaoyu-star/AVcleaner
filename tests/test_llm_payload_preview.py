from __future__ import annotations

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
            for table in ["scans", "plans", "runs", "quarantine_manifests", "llm_suggestions"]
        }


def test_llm_payload_preview_requires_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_llm_payload_preview_rejects_extra_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "source_path": "C:\\bad.mp4"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_llm_payload_preview_is_non_mutating_and_omits_full_path_by_default(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "ABP-123.mp4")
    plan = create_plan(client, auth_headers, tmp_path)
    item = next(row for row in plan["items"] if row["original_name"] == "movie_without_code.mp4")
    before = table_counts()

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert table_counts() == before
    assert body["full_path_included"] is False
    assert body["privacy"]["sends_full_path"] is False
    assert body["items"][0]["filename"] == "movie_without_code.mp4"
    assert body["items"][0]["full_path_included"] is False
    assert str(tmp_path) not in response.text
    assert "api_key" not in response.text.lower()
    assert body["items"][0]["neighbor_filenames"]


def test_llm_payload_preview_rejects_unknown_item(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        headers=auth_headers,
        json={"item_ids": ["not-real"], "include_neighbors": True},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_plan_item"
