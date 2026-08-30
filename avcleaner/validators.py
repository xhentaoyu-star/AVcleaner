from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Mapping

from .constants import WINDOWS_RESERVED_NAMES
from .enums import IssueCode, IssueSeverity, Operation
from .fingerprint import snapshot_for_path
from .models import FileSnapshot, PlanItem, ValidationIssue
from .paths import is_relative_to

INVALID_CHARS_RE = re.compile(r'[<>"\\/|?*]')
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f]")
BLOCKING = IssueSeverity.BLOCKING
WARNING = IssueSeverity.WARNING


def issue(code: IssueCode, severity: IssueSeverity = BLOCKING, **details: object) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        blocking=severity == IssueSeverity.BLOCKING,
        message_key=str(code),
        details={key: value for key, value in details.items() if value is not None},
    )


def validate_filename(target_name: str, original_extension: str, long_path_mode: str = "conservative") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not target_name or not target_name.strip():
        return [issue(IssueCode.EMPTY_NAME)]
    if CONTROL_CHARS_RE.search(target_name):
        issues.append(issue(IssueCode.CONTROL_CHARACTER))
    if INVALID_CHARS_RE.search(target_name):
        issues.append(issue(IssueCode.INVALID_CHARACTER))
    if ":" in target_name:
        issues.append(issue(IssueCode.ALTERNATE_DATA_STREAM))
        issues.append(issue(IssueCode.INVALID_CHARACTER))
    if target_name.endswith((" ", ".")):
        issues.append(issue(IssueCode.TRAILING_DOT_OR_SPACE))

    base = target_name.split(".", 1)[0].upper()
    has_extension = "." in target_name
    if base in WINDOWS_RESERVED_NAMES:
        issues.append(issue(IssueCode.RESERVED_NAME_WITH_EXTENSION if has_extension else IssueCode.RESERVED_NAME))

    if Path(target_name).suffix.lower() != original_extension.lower():
        issues.append(issue(IssueCode.EXTENSION_CHANGED))

    return issues


def _directory_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))


def _case_insensitive_directory_indexes(paths: list[Path]) -> dict[str, dict[str, Path]]:
    indexes: dict[str, dict[str, Path]] = {}
    for path in paths:
        parent = path.parent
        key = _directory_key(parent)
        if key in indexes:
            continue
        try:
            indexes[key] = {child.name.casefold(): child for child in parent.iterdir()} if parent.exists() else {}
        except OSError:
            indexes[key] = {}
    return indexes


def find_case_insensitive_existing(path: Path, directory_index: Mapping[str, Path] | None = None) -> Path | None:
    if directory_index is not None:
        return directory_index.get(path.name.casefold())
    parent = path.parent
    if not parent.exists():
        return None
    desired = path.name.lower()
    try:
        for child in parent.iterdir():
            if child.name.lower() == desired:
                return child
    except OSError:
        return None
    return None


def snapshot_changed(path: Path, snapshot: FileSnapshot | None) -> bool:
    if snapshot is None:
        return False
    try:
        current = snapshot_for_path(path)
    except OSError:
        return True
    return current.size != snapshot.size or current.modified_ns != snapshot.modified_ns or current.fingerprint != snapshot.fingerprint


def validate_item_paths(
    root: Path,
    item: PlanItem,
    long_path_mode: str = "conservative",
    existing_by_parent: Mapping[str, Mapping[str, Path]] | None = None,
) -> list[ValidationIssue]:
    issues = validate_filename(item.target_name or item.suggested_name, item.extension, long_path_mode)
    source = Path(item.source_path).resolve(strict=False)
    target = Path(item.target_path).resolve(strict=False)
    raw_source = os.path.abspath(item.source_path)
    raw_target = os.path.abspath(item.target_path)

    if not is_relative_to(source, root) or not is_relative_to(target, root):
        issues.append(issue(IssueCode.PATH_ESCAPE, source=str(source), target=str(target), root=str(root)))
    if not source.exists():
        issues.append(issue(IssueCode.SOURCE_MISSING, source=str(source)))
    elif snapshot_changed(source, item.snapshot):
        issues.append(issue(IssueCode.SOURCE_CHANGED, source=str(source)))

    if raw_source == raw_target:
        issues.append(issue(IssueCode.TARGET_SAME_AS_SOURCE, severity=WARNING, target=str(target)))
    if raw_source.lower() == raw_target.lower() and raw_source != raw_target:
        issues.append(issue(IssueCode.CASE_ONLY_RENAME, severity=WARNING, target=str(target)))

    directory_index = existing_by_parent.get(_directory_key(target.parent), {}) if existing_by_parent is not None else None
    existing = find_case_insensitive_existing(target, directory_index)
    if existing and str(existing).lower() != str(source).lower():
        if existing.name == target.name:
            issues.append(issue(IssueCode.TARGET_EXISTS, target=str(target)))
        else:
            issues.append(issue(IssueCode.TARGET_EXISTS_CASE_INSENSITIVE, target=str(target), existing=str(existing)))

    target_len = len(str(target))
    if long_path_mode == "conservative":
        if target_len > 259:
            issues.append(issue(IssueCode.PATH_TOO_LONG, target=str(target), length=target_len))
        elif target_len > 240:
            issues.append(issue(IssueCode.PATH_NEAR_LIMIT, severity=WARNING, target=str(target), length=target_len))
    elif target_len > 240:
        issues.append(issue(IssueCode.PATH_NEAR_LIMIT, severity=WARNING, target=str(target), length=target_len))
    return issues


def validate_conflicts(items: list[PlanItem]) -> dict[str, list[ValidationIssue]]:
    selected = [item for item in items if item.action in {Operation.RENAME, Operation.QUARANTINE, "rename", "quarantine"}]
    exact_counts = Counter(str(Path(item.target_path).resolve(strict=False)) for item in selected)
    lower_counts = Counter(str(Path(item.target_path).resolve(strict=False)).lower() for item in selected)
    by_item: dict[str, list[ValidationIssue]] = {item.id: [] for item in items}
    for item in selected:
        target = str(Path(item.target_path).resolve(strict=False))
        lower = target.lower()
        if exact_counts[target] > 1:
            by_item[item.id].append(issue(IssueCode.DUPLICATE_TARGET, target=target))
        elif lower_counts[lower] > 1:
            by_item[item.id].append(issue(IssueCode.DUPLICATE_TARGET_CASE_INSENSITIVE, target=target))
    return by_item


def validate_plan_items(root_path: str | Path, items: list[PlanItem], long_path_mode: str = "conservative") -> list[PlanItem]:
    root = Path(root_path).resolve(strict=False)
    conflict_issues = validate_conflicts(items)
    rename_targets = [
        Path(item.target_path).resolve(strict=False)
        for item in items
        if item.action in {Operation.RENAME, "rename"}
    ]
    existing_by_parent = _case_insensitive_directory_indexes(rename_targets)
    validated: list[PlanItem] = []
    for item in items:
        issues: list[ValidationIssue] = []
        if item.action in {Operation.RENAME, "rename"}:
            issues.extend(validate_item_paths(root, item, long_path_mode, existing_by_parent))
        elif item.action in {Operation.QUARANTINE, "quarantine"}:
            source = Path(item.source_path).resolve(strict=False)
            if not is_relative_to(source, root):
                issues.append(issue(IssueCode.PATH_ESCAPE, source=str(source), root=str(root)))
            if not source.exists():
                issues.append(issue(IssueCode.SOURCE_MISSING, source=str(source)))
            elif snapshot_changed(source, item.snapshot):
                issues.append(issue(IssueCode.SOURCE_CHANGED, source=str(source)))
        issues.extend(conflict_issues.get(item.id, []))
        requires_review = item.requires_review or any(problem.blocking for problem in issues)
        checked = item.checked and not any(problem.blocking for problem in issues)
        requires_two_step = item.requires_two_step or any(problem.code == IssueCode.CASE_ONLY_RENAME for problem in issues)
        previous_issue_codes = {str(problem.code) for problem in item.issues}
        rule_warnings = [warning for warning in item.warnings if warning not in previous_issue_codes]
        warnings = list(
            dict.fromkeys(
                [*rule_warnings, *(str(problem.code) for problem in issues if not problem.blocking)]
            )
        )
        validated.append(
            item.model_copy(
                update={
                    "issues": issues,
                    "warnings": warnings,
                    "requires_review": requires_review,
                    "checked": checked,
                    "requires_two_step": requires_two_step,
                }
            )
        )
    return validated


def has_blocking_issues(item: PlanItem) -> bool:
    return any(problem.blocking for problem in item.issues)
