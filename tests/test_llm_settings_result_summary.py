from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_llm_test_ui_has_readable_summary_fields() -> None:
    text = APP_JS.read_text(encoding="utf-8")

    assert "function renderLlmTestSummary" in text
    for field in [
        "compatibility_mode",
        "used_response_format_json_schema",
        "json_extracted",
        "schema_valid",
        "safety_valid",
        "error_code",
    ]:
        assert field in text


def test_llm_test_failure_keeps_stable_code_and_omits_secrets(client, auth_headers: dict[str, str]) -> None:
    response = client.post("/api/llm/test", headers=auth_headers, json={})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "llm_not_configured"
    text = response.text.lower()
    assert "api_key" not in text
    assert "authorization" not in text
    assert "bearer" not in text
    assert "traceback" not in text
