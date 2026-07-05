from __future__ import annotations

from pathlib import Path

from avcleaner.enums import IssueCode, IssueSeverity, Operation, SuggestionSource
from avcleaner.models import PlanItem, ValidationIssue
from avcleaner.planner import decorate_plan_item


def test_repeated_issue_codes_are_collapsed_on_plan_item() -> None:
    item = PlanItem(
        id="item1",
        source_path=str(Path("ABP-123.mp4")),
        source_rel_path="ABP-123.mp4",
        original_name="ABP-123.mp4",
        target_name="ABP-123.mp4",
        suggested_name="ABP-123.mp4",
        target_path=str(Path("ABP-123.mp4")),
        target_rel_path="ABP-123.mp4",
        action=Operation.RENAME,
        source=SuggestionSource.RULE,
        issues=[
            ValidationIssue(code=IssueCode.CASE_ONLY_RENAME, severity=IssueSeverity.WARNING),
            ValidationIssue(code=IssueCode.CASE_ONLY_RENAME, severity=IssueSeverity.WARNING),
        ],
    )

    decorated = decorate_plan_item(item)

    assert decorated.issue_codes == ["case_only_rename"]
    assert decorated.review_reason_codes.count("case_only_rename") <= 1


def test_frontend_deduplicates_issue_codes_before_display() -> None:
    source = (Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js").read_text(encoding="utf-8")

    assert "function issueCodes" in source
    assert "new Set" in source
