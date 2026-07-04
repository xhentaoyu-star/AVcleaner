from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import make_file

from avcleaner.llm import parse_llm_payload
from avcleaner.models import LLMBatchResponse, LLMSuggestion


def valid_payload(**overrides) -> dict:
    suggestion = {
        "item_id": "item-1",
        "suggested_name": "ABP-123.mp4",
        "media_code": "ABP-123",
        "part_suffix": "",
        "variant": "",
        "language_suffix": "",
        "removed_tokens": [],
        "confidence": 0.9,
        "reason": "ok",
        "warnings": [],
    }
    suggestion.update(overrides)
    return {"suggestions": [suggestion]}


@pytest.mark.parametrize(
    "payload",
    [
        "{not json",
        {"suggestions": [{"item_id": "x"}]},
        {"suggestions": [dict(valid_payload()["suggestions"][0], unexpected=True)]},
        valid_payload(confidence=1.5),
        valid_payload(warnings="bad"),
        valid_payload(removed_tokens="bad"),
    ],
)
def test_parse_llm_payload_rejects_invalid_structured_output(payload) -> None:
    with pytest.raises(ValueError):
        parse_llm_payload(payload if isinstance(payload, str) else json.dumps(payload))


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


@pytest.mark.parametrize(
    "suggested_name,expected_code",
    [
        ("", "empty_name"),
        ("ABP-123.mkv", "extension_changed"),
        ("CON.mp4", "reserved_name_with_extension"),
        ("ABP-123.mp4:evil", "alternate_data_stream"),
        ("nested/ABP-123.mp4", "invalid_character"),
    ],
)
def test_plan_llm_suggestion_records_invalid_filename_issues(
    suggested_name: str,
    expected_code: str,
    tmp_path: Path,
    client,
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name=suggested_name, media_code="ABP-123", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": False},
    )

    assert response.status_code == 200
    suggestion = response.json()["suggestions"][0]
    assert suggestion["status"] == "invalid"
    assert expected_code in [issue["code"] for issue in suggestion["validation_issues"]]


def test_invalid_suggestion_cannot_be_accepted(tmp_path: Path, client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    make_file(tmp_path, "movie_without_code.mp4")
    configure_mock_llm(client, auth_headers)
    plan = create_plan(client, auth_headers, tmp_path)
    item = plan["items"][0]

    async def fake_suggest(_request, _settings):
        return LLMBatchResponse(
            suggestions=[LLMSuggestion(item_id=item["id"], suggested_name="CON.mp4", media_code="CON", confidence=0.9)]
        )

    monkeypatch.setattr("avcleaner.llm.suggest_with_llm", fake_suggest)
    suggestion = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggest",
        headers=auth_headers,
        json={"item_ids": [item["id"]], "include_neighbors": True, "use_cache": False},
    ).json()["suggestions"][0]

    response = client.post(
        f"/api/plans/{plan['plan_id']}/llm/suggestions/{suggestion['suggestion_id']}/accept",
        headers=auth_headers,
        json={"expected_plan_hash": plan["plan_hash"]},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "blocking_suggestion"
