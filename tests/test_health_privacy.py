from __future__ import annotations


def test_health_is_token_protected_because_it_exposes_paths(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_health_response_does_not_expose_secrets_or_media_roots(client, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/health", headers=auth_headers)

    assert response.status_code == 200
    text = response.text.lower()
    assert "api_key" not in text
    assert "authorization" not in text
    assert "bearer" not in text
    assert "l:\\\\1\\\\media" not in text
    body = response.json()
    assert {"database_ok", "templates_ok", "static_ok", "keyring_ok", "mode"} <= set(body)
