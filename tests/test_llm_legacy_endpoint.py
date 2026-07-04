from __future__ import annotations

from avcleaner.database import connect


def count_rows(table: str) -> int:
    with connect() as conn:
        return conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]


def test_generic_llm_suggest_requires_token(client) -> None:
    response = client.post("/api/llm/suggest", json={"items": []})

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_generic_llm_suggest_is_disabled_and_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before = {table: count_rows(table) for table in ["scans", "plans", "runs", "llm_suggestions"]}

    response = client.post(
        "/api/llm/suggest",
        headers=auth_headers,
        json={
            "items": [
                {
                    "id": "x",
                    "name": "movie_without_code.mp4",
                    "extension": ".mp4",
                    "adjacent_names": [],
                    "path": "L:\\secret\\movie_without_code.mp4",
                }
            ]
        },
    )

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_llm_suggest_disabled"
    after = {table: count_rows(table) for table in before}
    assert after == before
