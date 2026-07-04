from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def configure_mock_llm(client, headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "ollama"
    settings["llm"]["model"] = "mock-model"
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def test_llm_schema_error_returns_stable_code(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)

    async def fake_suggest(_request, _settings):
        raise ValueError("bad schema")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": False},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "llm_schema_invalid"


def test_llm_provider_error_is_sanitized(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)

    async def fake_suggest(_request, _settings):
        raise RuntimeError("Authorization: Bearer secret-value")

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": False},
    )

    assert response.status_code == 502
    assert response.json()["error_code"] == "llm_provider_error"
    assert "secret-value" not in response.text


def test_llm_suggest_rejects_extra_fields(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": True, "target_path": "C:\\bad.mp4"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "request_extra_fields"
