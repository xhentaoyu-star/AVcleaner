from __future__ import annotations

from pathlib import Path

import pytest


def test_index_is_unprotected(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "avcleaner-token" in response.text


def test_capabilities_is_unprotected(client) -> None:
    response = client.get("/api/capabilities")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "localhost:8765",
        "127.0.0.1",
        "127.0.0.1:8765",
        "[::1]",
        "[::1]:8765",
    ],
)
def test_loopback_host_can_load_index(client, host: str) -> None:
    response = client.get("/", headers={"Host": host})

    assert response.status_code == 200
    assert "avcleaner-token" in response.text


@pytest.mark.parametrize(
    "host",
    [
        "evil.test",
        "evil.test:8765",
        "localhost.evil.test",
        "127.0.0.1.evil.test",
        "[::1].evil.test",
        "localhost:not-a-port",
        pytest.param("localhost:" + ("9" * 5000), id="oversized-port"),
    ],
)
def test_untrusted_host_cannot_read_api_token(client, host: str) -> None:
    response = client.get("/", headers={"Host": host})

    assert response.status_code == 400
    assert "avcleaner-token" not in response.text


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
