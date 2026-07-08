from __future__ import annotations

from avcleaner.database import connect


def _counts() -> tuple[int, int]:
    with connect() as conn:
        plans = conn.execute("SELECT COUNT(*) AS count FROM plans").fetchone()["count"]
        runs = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]
    return plans, runs


def test_rules_test_requires_token(client) -> None:
    response = client.post("/api/rules/test", json={"filename": "ABP-123.mp4"})

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_rules_test_rejects_wrong_token(client) -> None:
    response = client.post("/api/rules/test", headers={"X-AVCleaner-Token": "wrong"}, json={"filename": "ABP-123.mp4"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "api_token_invalid"


def test_rules_test_returns_suggestion_and_trace(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "FC2PPV1234567_1.mp4"})

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"]["suggested_name"] == "FC2-PPV-1234567-1.mp4"
    assert body["suggestion"]["trace"]
    assert isinstance(body["validation_preview"], list)


def test_rules_test_rejects_extra_fields(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "ABP-123.mp4", "source_path": "C:\\bad"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_rules_test_is_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before = _counts()

    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "HEYZO-1234.mp4"})

    assert response.status_code == 200
    assert _counts() == before
