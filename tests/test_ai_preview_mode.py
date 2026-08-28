from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import LLMBatchResponse, LLMSuggestion


def configure_llm(client, headers: dict[str, str]) -> None:
    settings = client.get("/api/settings", headers=headers).json()
    settings["llm"]["provider"] = "openai_compatible"
    settings["llm"]["base_url"] = "http://127.0.0.1:9"
    settings["llm"]["model"] = "mock-model"
    settings["llm"]["api_key"] = ""
    response = client.put("/api/settings", headers=headers, json=settings)
    assert response.status_code == 200


def test_ai_preview_applies_valid_suggestion_to_preview_only(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    source = make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    configure_llm(client, auth_headers)

    async def fake_suggest(request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=request.items[0].id,
                    suggested_name="ABP-123-A.mp4",
                    media_code="ABP-123",
                    variant="-A",
                    confidence=0.92,
                    reason="mock",
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    )

    assert response.status_code == 200
    item = response.json()["plan"]["items"][0]
    assert item["target_name"] == "ABP-123-A.mp4"
    assert item["source"] == "llm"
    assert item["llm_state"] == "applied_to_preview"
    assert item["manual_edited"] is False
    assert source.exists()
    assert not (tmp_path / "ABP-123-A.mp4").exists()


def test_ai_preview_capability_visible_when_llm_configured(client, auth_headers: dict[str, str]) -> None:
    configure_llm(client, auth_headers)

    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["preview_modes"] == ["rule", "ai"]
    assert response.json()["capabilities"]["ai_smart_preview"] is True


def test_ai_preview_reports_when_no_items_are_eligible_for_ai(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
) -> None:
    advertising_dir = tmp_path / "宣傳文件"
    advertising_dir.mkdir()
    (advertising_dir / "avmans最新导航地址.html").write_text("advertising", encoding="utf-8")
    configure_llm(client, auth_headers)

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["llm_used"] is False
    assert "ai_preview_no_eligible_items" in plan["messages"]
