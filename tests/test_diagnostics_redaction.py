from __future__ import annotations


def test_diagnostics_is_token_protected(client) -> None:
    response = client.get("/api/diagnostics")

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_diagnostics_redacts_paths_and_secrets(client, auth_headers: dict[str, str], tmp_path) -> None:
    response = client.get("/api/diagnostics", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    text = response.text.lower()

    assert str(tmp_path).lower() not in text
    assert "authorization" not in text
    assert "bearer" not in text
    assert "x-avcleaner-token" not in text
    assert body["app"]["version"] == "0.8.1"
    assert body["runtime"]["mode"] in {"dev", "portable", "appdata"}
    assert body["runtime"]["data_dir"].startswith("<")
    assert body["health"]["ok"] in {True, False}
    assert "data_dir" not in body["health"]
    assert body["endpoint_status"]["legacy_execute"] == "disabled"
    assert body["endpoint_status"]["generic_llm_suggest"] == "disabled"
    assert body["capabilities"]["diagnostics_panel"] is True
