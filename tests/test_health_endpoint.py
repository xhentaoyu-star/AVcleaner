from __future__ import annotations


def test_health_requires_token(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_health_reports_runtime_checks(client, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/health", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["version"] == "0.5.0"
    assert body["mode"] in {"dev", "portable", "appdata"}
    assert body["database_ok"] is True
    assert body["templates_ok"] is True
    assert body["static_ok"] is True
    assert body["data_dir_writable"] is True
    assert isinstance(body["keyring_ok"], bool)
    assert body["data_dir"]
    assert body["logs_dir"]
    assert body["quarantine_dir"]


def test_capabilities_exposes_v050_packaging_features(client) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.5.0"
    assert body["capabilities"]["packaging_ready"] is True
    assert body["capabilities"]["portable_mode"] is True
    assert body["capabilities"]["appdata_mode"] is True
    assert body["capabilities"]["health_check"] is True
    assert body["capabilities"]["legacy_llm_suggest_disabled"] is True
