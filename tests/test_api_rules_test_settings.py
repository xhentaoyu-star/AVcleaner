from __future__ import annotations

from avcleaner.database import connect


def db_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def test_rules_test_accepts_safe_settings_override(client, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/rules/test",
        headers=auth_headers,
        json={
            "filename": "ABP-123_2-C.mp4",
            "settings_override": {"output_template": "{code}{variant}{part}{language}{ext}"},
        },
    )

    assert response.status_code == 200
    assert response.json()["suggestion"]["suggested_name"] == "ABP-123-C-2.mp4"


def test_rules_test_rejects_invalid_settings_override_with_stable_code(client, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/rules/test",
        headers=auth_headers,
        json={"filename": "ABP-123.mp4", "settings_override": {"output_template": "{bad}{ext}"}},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_rule_settings"


def test_rules_test_settings_override_remains_non_mutating(client, auth_headers: dict[str, str]) -> None:
    before_counts = db_counts()
    before_settings = client.get("/api/settings/export", headers=auth_headers).json()["settings"]

    response = client.post(
        "/api/rules/test",
        headers=auth_headers,
        json={"filename": "customads.invalid@ABP-123.mp4", "settings_override": {"remove_ad_domains": ["customads.invalid"]}},
    )
    after_settings = client.get("/api/settings/export", headers=auth_headers).json()["settings"]

    assert response.status_code == 200
    assert response.json()["suggestion"]["suggested_name"] == "ABP-123.mp4"
    assert db_counts() == before_counts
    assert after_settings == before_settings
