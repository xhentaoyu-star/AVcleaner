from __future__ import annotations

from pathlib import Path

import pytest

from avcleaner.enums import IssueCode
from avcleaner.models import PlanItem
from avcleaner.scanner import scan_files
from avcleaner.models import ScanRequest
from avcleaner.validator import validate_target_name
from avcleaner.validators import validate_conflicts, validate_plan_items


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("", IssueCode.EMPTY_NAME),
        ("ABP:123.mp4", IssueCode.ALTERNATE_DATA_STREAM),
        ("ABP<123.mp4", IssueCode.INVALID_CHARACTER),
        ("ABP-123 .mp4 ", IssueCode.TRAILING_DOT_OR_SPACE),
        ("CON.mp4", IssueCode.RESERVED_NAME_WITH_EXTENSION),
        ("NUL", IssueCode.RESERVED_NAME),
        ("COM1.avi", IssueCode.RESERVED_NAME_WITH_EXTENSION),
        ("LPT9.mkv", IssueCode.RESERVED_NAME_WITH_EXTENSION),
        ("ABP-123.mkv", IssueCode.EXTENSION_CHANGED),
        ("ABP-\x01.mp4", IssueCode.CONTROL_CHARACTER),
    ],
)
def test_validate_target_name_issue_codes(name: str, expected: IssueCode) -> None:
    assert str(expected) in validate_target_name(name, ".mp4")


def _plan_item(root: Path, source_name: str, target_name: str) -> PlanItem:
    source = root / source_name
    source.write_bytes(b"video")
    scan = scan_files(ScanRequest(root_path=str(root)))
    item = next(row for row in scan.files if row.name == source_name)
    return PlanItem(
        id=source_name,
        scan_item_id=item.id,
        source_path=str(source),
        source_rel_path=source.name,
        original_name=source.name,
        target_name=target_name,
        suggested_name=target_name,
        target_path=str(source.with_name(target_name)),
        target_rel_path=target_name,
        action="rename",
        operation="rename",
        source="rule",
        suggestion_source="rule",
        extension=source.suffix,
        snapshot=item.snapshot,
    )


def test_validate_path_escape_is_blocking(tmp_path: Path) -> None:
    item = _plan_item(tmp_path, "old.mp4", "new.mp4")
    escaped = item.model_copy(update={"target_path": str(tmp_path.parent / "new.mp4")})

    validated = validate_plan_items(tmp_path, [escaped])[0]

    assert any(issue.code == IssueCode.PATH_ESCAPE and issue.blocking for issue in validated.issues)
    assert not validated.checked


def test_validate_target_exists_blocks(tmp_path: Path) -> None:
    item = _plan_item(tmp_path, "old.mp4", "new.mp4")
    (tmp_path / "new.mp4").write_bytes(b"existing")

    validated = validate_plan_items(tmp_path, [item])[0]

    assert any(issue.code == IssueCode.TARGET_EXISTS for issue in validated.issues)


def test_validate_case_only_rename_warns(tmp_path: Path) -> None:
    item = _plan_item(tmp_path, "abp-123.mp4", "ABP-123.mp4")

    validated = validate_plan_items(tmp_path, [item])[0]

    assert any(issue.code == IssueCode.CASE_ONLY_RENAME and not issue.blocking for issue in validated.issues)
    assert validated.requires_two_step


def test_validate_duplicate_target_blocks(tmp_path: Path) -> None:
    a = _plan_item(tmp_path, "a.mp4", "ABP-123.mp4")
    b = _plan_item(tmp_path, "b.mp4", "ABP-123.mp4")

    issues = validate_conflicts([a, b])

    assert any(issue.code == IssueCode.DUPLICATE_TARGET for issue in issues[a.id])
    assert any(issue.code == IssueCode.DUPLICATE_TARGET for issue in issues[b.id])


def test_validate_source_changed_blocks(tmp_path: Path) -> None:
    item = _plan_item(tmp_path, "old.mp4", "new.mp4")
    (tmp_path / "old.mp4").write_bytes(b"changed")

    validated = validate_plan_items(tmp_path, [item])[0]

    assert any(issue.code == IssueCode.SOURCE_CHANGED for issue in validated.issues)


def test_validate_near_long_path_warns(tmp_path: Path) -> None:
    item = _plan_item(tmp_path, "old.mp4", ("a" * 230) + ".mp4")

    validated = validate_plan_items(tmp_path, [item])[0]

    assert any(issue.code in {IssueCode.PATH_NEAR_LIMIT, IssueCode.PATH_TOO_LONG} for issue in validated.issues)


def test_validate_plan_enumerates_each_target_directory_once(tmp_path: Path, monkeypatch) -> None:
    first = _plan_item(tmp_path, "old-a.mp4", "new-a.mp4")
    second = _plan_item(tmp_path, "old-b.mp4", "new-b.mp4")
    real_iterdir = Path.iterdir
    enumerations = 0

    def counted_iterdir(path: Path):
        nonlocal enumerations
        if path.resolve(strict=False) == tmp_path.resolve(strict=False):
            enumerations += 1
        return real_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", counted_iterdir)

    validate_plan_items(tmp_path, [first, second])

    assert enumerations == 1
