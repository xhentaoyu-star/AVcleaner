from __future__ import annotations

from pathlib import Path

from avcleaner.llm_test_status import llm_settings_fingerprint
from avcleaner.models import LLMSettings


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def test_llm_test_status_is_visible_and_loaded_on_startup() -> None:
    html = HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    for marker in [
        'id="llmTestStatus"',
        'id="llmTestStatusLabel"',
        'id="llmTestStatusDetail"',
        'id="llmTestStatusTime"',
    ]:
        assert marker in html

    for marker in [
        "function renderLlmTestStatus",
        "async function loadLlmTestStatus",
        "function markLlmSettingsChanged",
        "await loadLlmTestStatus()",
    ]:
        assert marker in app_js


def test_failed_llm_test_status_is_persisted_without_secrets(client, auth_headers: dict[str, str]) -> None:
    initial = client.get("/api/llm/test-status", headers=auth_headers)
    assert initial.status_code == 200
    assert initial.json()["status"] == "not_tested"

    tested = client.post("/api/llm/test", headers=auth_headers, json={})
    assert tested.status_code == 200
    assert tested.json()["ok"] is False

    response = client.get("/api/llm/test-status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["provider"] == "disabled"
    assert body["error_code"] == "llm_not_configured"
    assert body["tested_at"]
    serialized = response.text.lower()
    for secret_name in ["api_key", "base_url", "payload_preview", "authorization", "bearer"]:
        assert secret_name not in serialized


def test_llm_test_status_marks_changed_settings_as_needing_retest(client, auth_headers: dict[str, str]) -> None:
    tested = client.post("/api/llm/test", headers=auth_headers, json={})
    assert tested.status_code == 200

    settings = client.get("/api/settings", headers=auth_headers).json()
    settings["llm"]["model"] = "changed-after-test"
    saved = client.put("/api/settings", headers=auth_headers, json=settings)
    assert saved.status_code == 200

    status = client.get("/api/llm/test-status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "settings_changed"


def test_llm_test_fingerprint_changes_when_api_key_changes() -> None:
    first = LLMSettings(provider="openai_compatible", model="gpt-5", api_key="first-secret")
    second = first.model_copy(update={"api_key": "second-secret"})

    assert llm_settings_fingerprint(first) != llm_settings_fingerprint(second)
