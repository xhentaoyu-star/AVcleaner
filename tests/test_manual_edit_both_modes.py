from __future__ import annotations

from pathlib import Path

from conftest import make_file

from avcleaner.models import LLMBatchResponse, LLMSuggestion

from test_ai_preview_mode import configure_llm


def test_manual_edit_after_ai_preview_sets_manual_source_and_updates_hash(
    tmp_path: Path,
    client,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")
    configure_llm(client, auth_headers)

    async def fake_suggest(request, _settings):
        return LLMBatchResponse(
            suggestions=[
                LLMSuggestion(
                    item_id=request.items[0].id,
                    suggested_name="ABP-123-A.mp4",
                    confidence=0.9,
                    reason="mock",
                )
            ]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    plan = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "ai"},
    ).json()["plan"]
    item = plan["items"][0]

    response = client.patch(
        f"/api/plans/{plan['plan_id']}/items/{item['id']}",
        headers=auth_headers,
        json={"target_name": "ABP-123-B.mp4"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_hash"] != plan["plan_hash"]
    assert body["item"]["target_name"] == "ABP-123-B.mp4"
    assert body["item"]["source"] == "manual"
    assert body["item"]["manual_edited"] is True
