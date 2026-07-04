from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.database import connect
from avcleaner.models import LLMBatchResponse, LLMSuggestion


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
    settings["llm"]["base_url"] = "http://127.0.0.1:11434"
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def run_count() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()["count"]


def test_llm_suggest_requires_token(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "api_token_missing"


def test_llm_suggest_rejects_unknown_items(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": ["not-real"], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_plan_item"


def test_llm_suggest_requires_configured_provider(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    plan = create_plan(client, auth_headers, tmp_path)

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [plan["items"][0]["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "llm_not_configured"


def test_llm_suggest_stores_review_only_suggestion_without_modifying_plan(
    tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(request, _settings):
        assert not request.items[0].path
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=item["id"],
                    suggested_name="ABP-123.mp4",
                    media_code="ABP-123",
                    confidence=0.91,
                    reason="mock",
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    before_runs = run_count()
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"][0]["status"] == "valid"
    assert body["suggestions"][0]["suggested_name"] == "ABP-123.mp4"
    assert body["suggestions"][0]["validation_issues"] == []
    assert run_count() == before_runs
    stored_plan = client.get(f"/api/plans/{plan['plan_id']}", headers=auth_headers).json()
    assert stored_plan["items"][0]["target_name"] == item["target_name"]
    assert stored_plan["items"][0]["selected"] is False


def test_llm_suggestions_list_endpoint(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True},
    )

    response = client.get(f"/api/plans/{plan['plan_id']}/llm/suggestions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["plan_id"] == plan["plan_id"]
    assert response.json()["suggestions"][0]["item_id"] == item["id"]
