from __future__ import annotations

from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.models import LLMBatchResponse, LLMSuggestion


def create_plan(client, headers: dict[str, str], root: Path) -> dict:
    scan = client.post("/api/scan", json={"root_path": str(root), "recursive": True}, headers=headers)
    assert scan.status_code == 200
    plan = client.post("/api/plans", json={"scan_id": scan.json()["scan_id"]}, headers=headers)
    assert plan.status_code == 200
    return plan.json()


def configure_mock_llm(client, headers: dict[str, str], model: str = "mock-model") -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "ollama"
    settings["llm"]["model"] = model
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def test_llm_cache_hit_avoids_provider_call(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    calls = {"count": 0}

    async def fake_suggest(_request, _settings):
        calls["count"] += 1
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    payload = {"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True}

    first = client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)
    second = client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["suggestions"][0]["suggested_name"] == "ABP-123.mp4"


def test_llm_cache_key_changes_with_model(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers, model="mock-a")
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    calls = {"count": 0}

    async def fake_suggest(_request, _settings):
        calls["count"] += 1
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name=f"ABP-12{calls['count']}.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    payload = {"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True}
    first = client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)
    assert first.status_code == 200

    configure_mock_llm(client, auth_headers, model="mock-b")
    second = client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)

    assert second.status_code == 200
    assert calls["count"] == 2


def test_llm_cache_can_be_bypassed(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]
    calls = {"count": 0}

    async def fake_suggest(_request, _settings):
        calls["count"] += 1
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    payload = {"item_ids": [item["id"]], "include_neighbors": True, "use_cache": False}
    client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)
    client.post(f"/api/plans/{plan['plan_id']}/llm/suggest", headers=auth_headers, json=payload)

    assert calls["count"] == 2
