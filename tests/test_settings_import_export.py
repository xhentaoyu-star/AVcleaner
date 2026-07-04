from __future__ import annotations

from avcleaner.database import connect
from avcleaner.settings_store import get_settings


def db_counts() -> dict[str, int]:
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ["scans", "plans", "runs", "quarantine_manifests"]
        }


def test_settings_export_requires_token(client) -> None:
    missing = client.get("/api/settings/export")
    wrong = client.get("/api/settings/export", headers={"X-AVCleaner-Token": "wrong"})

    assert missing.status_code == 401
    assert missing.json()["error_code"] == "api_token_missing"
    assert wrong.status_code == 403
    assert wrong.json()["error_code"] == "api_token_invalid"


def test_settings_export_omits_api_key(client, auth_headers: dict[str, str]) -> None:
    settings = get_settings()
    payload = settings.model_copy(update={"llm": settings.llm.model_copy(update={"provider": "openai_compatible", "api_key": "secret"})})
    put_response = client.put("/api/settings", headers=auth_headers, json=payload.model_dump(mode="json"))
    assert put_response.status_code == 200

    response = client.get("/api/settings/export", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["app_version"]
    assert body["format_version"] == 1
    assert "api_key" not in body["settings"]["llm"]
    assert "secret" not in str(body)


def test_settings_import_dry_run_does_not_write(client, auth_headers: dict[str, str]) -> None:
    before = client.get("/api/settings/export", headers=auth_headers).json()["settings"]
    imported = dict(before)
    imported["rules"] = {**imported["rules"], "output_template": "{code}{variant}{part}{language}{ext}"}

    response = client.post("/api/settings/import", headers=auth_headers, json={"settings": imported, "dry_run": True})
    after = client.get("/api/settings/export", headers=auth_headers).json()["settings"]

    assert response.status_code == 200
    assert response.json()["dry_run"] is True
    assert response.json()["applied"] is False
    assert after == before


def test_settings_import_write_updates_non_secret_settings(client, auth_headers: dict[str, str]) -> None:
    exported = client.get("/api/settings/export", headers=auth_headers).json()["settings"]
    exported["rules"] = {**exported["rules"], "output_template": "{code}{variant}{part}{language}{ext}"}
    exported["llm"] = {**exported["llm"], "provider": "openai_compatible", "api_key": "must_not_import"}

    response = client.post("/api/settings/import", headers=auth_headers, json={"settings": exported, "dry_run": False})
    saved = client.get("/api/settings/export", headers=auth_headers).json()["settings"]

    assert response.status_code == 200
    assert response.json()["applied"] is True
    assert "llm_api_key_ignored" in response.json()["warnings"]
    assert saved["rules"]["output_template"] == "{code}{variant}{part}{language}{ext}"
    assert "api_key" not in saved["llm"]
    assert "must_not_import" not in str(saved)


def test_settings_import_invalid_returns_stable_code(client, auth_headers: dict[str, str]) -> None:
    exported = client.get("/api/settings/export", headers=auth_headers).json()["settings"]
    exported["rules"] = {**exported["rules"], "output_template": "{bad}{ext}"}

    response = client.post("/api/settings/import", headers=auth_headers, json={"settings": exported, "dry_run": False})

    assert response.status_code == 422
    assert response.json()["error_code"] == "settings_import_invalid"


def test_settings_import_rejects_extra_fields(client, auth_headers: dict[str, str]) -> None:
    exported = client.get("/api/settings/export", headers=auth_headers).json()["settings"]

    response = client.post(
        "/api/settings/import",
        headers=auth_headers,
        json={"settings": exported, "dry_run": True, "source_path": "C:\\bad"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"


def test_settings_import_is_non_mutating_for_filesystem_records(client, auth_headers: dict[str, str]) -> None:
    exported = client.get("/api/settings/export", headers=auth_headers).json()["settings"]
    before = db_counts()

    response = client.post("/api/settings/import", headers=auth_headers, json={"settings": exported, "dry_run": False})

    assert response.status_code == 200
    assert db_counts() == before


def test_legacy_execute_remains_disabled_after_settings_import(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/execute", headers=auth_headers, json={"confirm": True, "items": []})

    assert response.status_code == 410
    assert response.json()["error_code"] == "legacy_execute_disabled"
