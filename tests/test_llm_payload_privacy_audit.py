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


def configure_mock_llm(client, headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "ollama"
    settings["llm"]["model"] = "mock-model"
    settings["llm"]["api_key"] = "secret-key-value"
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def test_payload_preview_does_not_expose_paths_or_secrets(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/payload-preview",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True},
    )

    assert response.status_code == 200
    text = response.text
    assert str(tmp_path) not in text
    assert item["source_path"] not in text
    assert item["target_path"] not in text
    assert "C:\\" not in text
    assert "L:\\" not in text
    assert "Users" not in text
    assert "secret-key-value" not in text
    assert "Authorization" not in text
    body = response.json()
    assert body["full_path_included"] is False
    assert body["privacy"]["sends_full_path"] is False


def test_suggestion_generation_sends_only_approved_fields_by_default(
    tmp_path: Path, client, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    make_file(tmp_path, "nearby_ABP-124.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = next(row for row in plan["items"] if row["original_name"] == "movie_without_code.mp4")
    captured: dict = {}

    async def fake_suggest(request, _settings):
        sent = request.items[0]
        captured.update(sent.model_dump(mode="json"))
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="ABP-123.mp4", media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": False},
    )

    assert response.status_code == 200
    assert captured["name"] == "movie_without_code.mp4"
    assert captured["extension"] == ".mp4"
    assert captured["adjacent_names"] == ["nearby_ABP-124.mp4"]
    assert captured["rule_suggested_name"] == item["target_name"]
    assert "media_code" in captured
    assert "sidecar_type" in captured
    assert "language_suffix" in captured
    assert captured["path"] is None
    assert "source_path" not in captured
    assert "target_path" not in captured


def test_send_full_path_setting_defaults_false(client, auth_headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=auth_headers).json()

    assert settings["llm"]["send_full_path"] is False
