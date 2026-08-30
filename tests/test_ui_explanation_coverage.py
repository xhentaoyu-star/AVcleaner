from __future__ import annotations

import re
from pathlib import Path

from avcleaner.enums import IssueCode, RunItemState, RunState


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"


def _source() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _has_entry(text: str, code: str) -> bool:
    return bool(
        re.search(
            rf'"{re.escape(code)}"\s*:\s*\{{(?=[^}}]*title\s*:)(?=[^}}]*explanation\s*:)(?=[^}}]*suggested_action\s*:)',
            text,
            re.DOTALL,
        )
    )


def test_all_backend_issue_codes_have_frontend_explanations() -> None:
    text = _source()

    missing = [str(code) for code in IssueCode if not _has_entry(text, str(code))]

    assert missing == []


def test_common_gui_reason_codes_have_frontend_explanations() -> None:
    text = _source()
    reason_codes = [
        "download_residue_or_shortcut",
        "empty_file",
        "advertising_text_or_html_file",
        "custom_junk_keyword",
        "low_confidence",
        "media_code_not_detected",
        "detected_media_code",
        "kept",
        "already_clean",
        "sidecar_suggested_rename",
        "sidecar_already_clean",
        "sidecar_unmatched",
        "image_default_off",
        "nfo_default_off",
        "subtitle_sidecar",
        "sidecar_default_off",
        "blocking",
        "not_executable",
        "large_temp_file_requires_manual_selection",
        "unrecognized_filename_text",
        "configured_part_suffix_removal",
        "configured_variant_removal",
        "quarantine_inside_scan_root",
        "quarantine_recovery_required",
        "quarantine_recovered",
        "rollback_recovered",
        "operation_interrupted",
    ]

    missing = [code for code in reason_codes if not _has_entry(text, code)]

    assert missing == []


def test_run_statuses_have_frontend_explanations() -> None:
    text = _source()
    missing = [str(code) for code in [*RunState, *RunItemState] if not _has_entry(text, str(code))]

    assert missing == []


def test_unknown_code_falls_back_safely() -> None:
    text = _source()

    assert "function explanationFor" in text
    assert "未知状态" in text
    assert "raw_code" in text
    assert "severity" in text
