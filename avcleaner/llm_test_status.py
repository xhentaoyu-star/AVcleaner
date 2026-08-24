from __future__ import annotations

import hashlib
import json

from .database import utc_now_iso
from .models import LLMSettings, LLMTestResponse, LLMTestStatusResponse
from .repository import get_local_ui_state, set_local_ui_state


LLM_TEST_STATUS_KEY = "llm_test_status"


def llm_settings_fingerprint(settings: LLMSettings) -> str:
    encoded = json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_payload() -> dict:
    raw = get_local_ui_state(LLM_TEST_STATUS_KEY)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_llm_test_status(settings: LLMSettings) -> LLMTestStatusResponse:
    payload = _load_payload()
    if not payload:
        return LLMTestStatusResponse()
    stored_fingerprint = str(payload.pop("settings_fingerprint", ""))
    try:
        status = LLMTestStatusResponse.model_validate(payload)
    except ValueError:
        return LLMTestStatusResponse()
    if stored_fingerprint != llm_settings_fingerprint(settings):
        return status.model_copy(update={"status": "settings_changed"})
    return status


def record_llm_test_status(settings: LLMSettings, response: LLMTestResponse) -> LLMTestStatusResponse:
    status = LLMTestStatusResponse(
        status="passed" if response.ok else "failed",
        tested_at=utc_now_iso(),
        provider=response.provider,
        model=response.model,
        compatibility_mode=response.compatibility_mode,
        latency_ms=response.latency_ms,
        schema_valid=response.schema_valid,
        safety_valid=response.safety_valid,
        error_code=response.error_code,
    )
    payload = status.model_dump(mode="json")
    payload["settings_fingerprint"] = llm_settings_fingerprint(settings)
    set_local_ui_state(LLM_TEST_STATUS_KEY, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return status
