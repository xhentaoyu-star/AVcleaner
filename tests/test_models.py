from __future__ import annotations

import pytest
from pydantic import ValidationError

from avcleaner.enums import IssueCode, Operation, RunState
from avcleaner.models import AppSettings, FileSnapshot, PlanExecuteRequest, ValidationIssue


def test_plan_execute_request_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        PlanExecuteRequest(selected_item_ids=["x"], confirm=True, plan_hash="h", items=[])  # type: ignore[call-arg]


def test_file_snapshot_fields_are_explicit() -> None:
    snapshot = FileSnapshot(size=1, created_ns=2, modified_ns=3, fingerprint="abc")
    assert snapshot.model_dump() == {"size": 1, "created_ns": 2, "modified_ns": 3, "fingerprint": "abc"}


def test_app_settings_defaults_are_v3() -> None:
    settings = AppSettings()
    assert settings.schema_version == 3
    assert settings.filesystem.long_path_mode == "conservative"
    assert settings.rename.auto_cd_conflict is False


def test_validation_issue_uses_stable_code() -> None:
    issue = ValidationIssue(code=IssueCode.TARGET_EXISTS, severity="blocking", blocking=True)
    assert issue.code == IssueCode.TARGET_EXISTS
    assert issue.message_key == ""


def test_enums_serialize_to_values() -> None:
    assert str(Operation.RENAME) == "rename"
    assert str(RunState.INTERRUPTED) == "interrupted"
