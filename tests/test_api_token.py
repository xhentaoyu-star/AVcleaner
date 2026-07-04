from __future__ import annotations

from pathlib import Path


def test_index_is_unprotected(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "avcleaner-token" in response.text


def test_capabilities_is_unprotected(client) -> None:
    response = client.get("/api/capabilities")
    assert response.status_code == 200


def test_scan_requires_token(tmp_path: Path, client) -> None:
    response = client.post("/api/scan", json={"root_path": str(tmp_path)})
    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_scan_rejects_invalid_token(tmp_path: Path, client) -> None:
    response = client.post("/api/scan", json={"root_path": str(tmp_path)}, headers={"X-AVCleaner-Token": "bad"})
    assert response.status_code == 403
    assert response.json()["error_code"] == "api_token_invalid"


def test_settings_requires_token(client) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 401


def test_runs_requires_token(client) -> None:
    response = client.get("/api/runs")
    assert response.status_code == 401


def test_llm_test_requires_token(client) -> None:
    response = client.post("/api/llm/test", json={})
    assert response.status_code == 401


def test_settings_with_token_succeeds(client, auth_headers) -> None:
    response = client.get("/api/settings", headers=auth_headers)
    assert response.status_code == 200
