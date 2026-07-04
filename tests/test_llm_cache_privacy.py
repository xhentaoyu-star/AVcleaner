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
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def cache_rows() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT cache_key, payload_hash, output_json FROM llm_suggestion_cache").fetchall()
    return [dict(row) for row in rows]


def test_cache_rows_do_not_include_full_paths_by_default(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 200
    serialized_rows = repr(cache_rows())
    assert str(tmp_path) not in serialized_rows
    assert item["source_path"] not in serialized_rows
    assert item["target_path"] not in serialized_rows
    assert "C:\\" not in serialized_rows
    assert "L:\\" not in serialized_rows


def test_invalid_suggestion_is_not_cached_as_valid(tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="C:\\Temp\\ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": True},
    )

    assert response.status_code == 200
    assert response.json()["suggestions"][0]["status"] == "invalid"
    assert cache_rows() == []
