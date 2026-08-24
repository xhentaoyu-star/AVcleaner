from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def _frontend_source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _assert_explanation_entry(text: str, code: str) -> None:
    pattern = (
        rf'"{re.escape(code)}"\s*:\s*\{{'
        rf"(?=[^}}]*title\s*:)"
        rf"(?=[^}}]*explanation\s*:)"
        rf"(?=[^}}]*suggested_action\s*:)"
    )
    assert re.search(pattern, text, re.DOTALL), f"missing structured UI explanation for {code}"


def test_common_issue_codes_have_frontend_explanations() -> None:
    text = _frontend_source()

    for code in [
        "case_only_rename",
        "target_exists",
        "target_exists_case_insensitive",
        "duplicate_target",
        "duplicate_target_case_insensitive",
        "extension_changed",
        "path_escape",
        "path_too_long",
        "source_missing",
        "source_changed",
        "file_in_use",
        "requires_review_item_selected",
        "blocking_item_selected",
        "plan_hash_mismatch",
        "no_selected_items",
        "manual_edit_conflict",
    ]:
        _assert_explanation_entry(text, code)


def test_review_reason_and_sidecar_reason_codes_have_frontend_explanations() -> None:
    text = _frontend_source()

    for code in [
        "low_confidence",
        "media_code_not_detected",
        "detected_media_code",
        "sidecar_suggested_rename",
        "sidecar_already_clean",
        "sidecar_unmatched",
        "obvious_advertising_filename",
        "image_default_off",
        "nfo_default_off",
        "subtitle_sidecar",
    ]:
        _assert_explanation_entry(text, code)


def test_llm_error_codes_have_frontend_explanations() -> None:
    text = _frontend_source()

    for code in [
        "llm_not_configured",
        "llm_auth_failed",
        "llm_request_failed",
        "llm_timeout",
        "llm_invalid_json",
        "llm_no_json_object",
        "llm_schema_invalid",
        "llm_suggestion_invalid",
        "llm_payload_privacy_violation",
        "legacy_llm_suggest_disabled",
    ]:
        _assert_explanation_entry(text, code)
