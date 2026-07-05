from __future__ import annotations

from pathlib import Path

from conftest import make_file


def test_rule_preview_items_expose_hidden_llm_state(tmp_path: Path, client, auth_headers: dict[str, str]) -> None:
    make_file(tmp_path, "hhd800.com@ABP-123.mp4")

    response = client.post(
        "/api/analyze",
        headers=auth_headers,
        json={"root_path": str(tmp_path), "preview_mode": "rule"},
    )

    assert response.status_code == 200
    item = response.json()["plan"]["items"][0]
    assert item["llm_state"] == "hidden"
    assert item["llm_error_code"] == ""
    assert item["llm_suggested_name"] == ""
