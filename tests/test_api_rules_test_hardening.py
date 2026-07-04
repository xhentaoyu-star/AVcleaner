from __future__ import annotations

import json

from avcleaner.database import connect


def db_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def settings_payload() -> str:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'app'").fetchone()
    return row["value"] if row else ""


def test_rules_test_hardening_rejects_missing_and_wrong_token(client) -> None:
    missing = client.post("/api/rules/test", json={"filename": "ABP-123.mp4"})
    wrong = client.post("/api/rules/test", headers={"X-AVCleaner-Token": "wrong"}, json={"filename": "ABP-123.mp4"})

    assert missing.status_code == 401
    assert missing.json()["error_code"] == "api_token_missing"
    assert wrong.status_code == 403
    assert wrong.json()["error_code"] == "api_token_invalid"


def test_rules_test_hardening_valid_token_returns_trace_and_validation(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "FC2PPV1234567_1.mp4"})

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"]["trace"]
    assert body["validation_preview"] == []


def test_rules_test_hardening_rejects_extra_fields(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "ABP-123.mp4", "target_path": "C:\\bad"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_rules_test_hardening_empty_filename_has_stable_error(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "   "})

    assert response.status_code == 400
    assert response.json()["error_code"] == "filename_required"


def test_rules_test_hardening_too_long_filename_has_stable_error(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "A" * 260 + ".mp4"})

    assert response.status_code == 400
    assert response.json()["error_code"] == "filename_too_long"


def test_rules_test_hardening_is_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before_counts = db_counts()
    before_settings = settings_payload()

    response = client.post(
        "/api/rules/test",
        headers=auth_headers,
        json={"filename": "HEYZO-1234.mp4", "settings_override": {"remove_bracket_ads": False}},
    )

    assert response.status_code == 200
    assert db_counts() == before_counts
    assert settings_payload() == before_settings


def test_rules_test_hardening_does_not_call_llm(client, auth_headers: dict[str, str], monkeypatch) -> None:
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("LLM must not be called by /api/rules/test")

    monkeypatch.setattr("avcleaner.app.suggest_with_llm", fail_if_called)

    response = client.post("/api/rules/test", headers=auth_headers, json={"filename": "ABP-123.mp4"})

    assert response.status_code == 200
