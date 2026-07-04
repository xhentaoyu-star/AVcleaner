from __future__ import annotations

import csv
import hashlib
import io
from collections import Counter
from pathlib import Path

from .database import dumps, utc_now_iso
from .enums import IssueCode, Operation, PlanState, SuggestionSource
from .errors import AppError
from .models import (
    ExecutionSummaryRequest,
    ExecutionSummaryResponse,
    PlanItem,
    PlanItemPatchResponse,
    PlanRecord,
    PlanRequest,
    PlanResponse,
    PlanSelectionRequest,
    PlanSelectionResponse,
    RuleConfig,
    ScanItem,
    RuleTraceStep,
)
from .repository import get_plan, get_scan, mark_llm_suggestions_stale, new_id, save_plan
from .rules import is_junk_file, suggest_name_with_trace
from .sidecars import classify_sidecar_type, group_id_for_media_code
from .validators import validate_filename, validate_plan_items


EXECUTABLE_ACTIONS = {Operation.RENAME, Operation.QUARANTINE, "rename", "quarantine"}
CONFLICT_CODES = {
    str(IssueCode.DUPLICATE_TARGET),
    str(IssueCode.DUPLICATE_TARGET_CASE_INSENSITIVE),
    str(IssueCode.TARGET_EXISTS),
    str(IssueCode.TARGET_EXISTS_CASE_INSENSITIVE),
}


def canonical_plan_items(items: list[PlanItem]) -> list[dict]:
    return [
        {
            "operation": str(item.operation or item.action),
            "source_rel_path": item.source_rel_path,
            "target_rel_path": item.target_rel_path,
            "target_name": item.target_name,
            "confidence": round(item.confidence, 6),
            "issues": sorted(str(issue.code) for issue in item.issues),
            "requires_two_step": item.requires_two_step,
            "trace": [
                {
                    "rule_id": step.rule_id,
                    "before": step.before,
                    "after": step.after,
                    "removed_tokens": step.removed_tokens,
                    "preserved_tokens": step.preserved_tokens,
                    "confidence_delta": step.confidence_delta,
                    "warnings": step.warnings,
                }
                for step in item.trace
            ],
            "group_id": item.group_id,
            "sidecar_type": item.sidecar_type,
            "associated_media_code": item.associated_media_code,
            "language_suffix": item.language_suffix,
            "sidecar_role": item.sidecar_role,
            "selected_default": item.selected_default,
            "selected": item.selected,
            "requires_review": item.requires_review,
            "review_reason_codes": item.review_reason_codes,
            "manual_edited": item.manual_edited,
            "last_edited_at": item.last_edited_at,
            "llm_accepted": item.llm_accepted,
            "llm_suggestion_id": item.llm_suggestion_id,
            "ruleset_hash": item.ruleset_hash,
        }
        for item in sorted(items, key=lambda row: row.id)
    ]


def compute_ruleset_hash(rules: RuleConfig) -> str:
    return hashlib.sha256(dumps(rules.model_dump(mode="json")).encode("utf-8")).hexdigest()


def compute_plan_hash(items: list[PlanItem]) -> str:
    return hashlib.sha256(dumps(canonical_plan_items(items)).encode("utf-8")).hexdigest()


def _issue_codes(item: PlanItem) -> list[str]:
    return [str(issue.code) for issue in item.issues]


def _review_reason_codes(item: PlanItem) -> list[str]:
    codes: list[str] = []
    if item.requires_review and item.confidence < 0.7:
        codes.append("low_confidence")
    if item.requires_review and not item.media_code and item.action in {Operation.REVIEW, "review"}:
        codes.append("media_code_not_detected")
    codes.extend(str(warning) for warning in item.warnings if warning)
    codes.extend(str(issue.code) for issue in item.issues if issue.blocking)
    return sorted(set(codes))


def _is_safe_selectable(item: PlanItem) -> bool:
    action = item.operation or item.action
    return (
        action in EXECUTABLE_ACTIONS
        and not item.blocking
        and not item.requires_review
        and not item.sidecar_type
    )


def decorate_plan_item(item: PlanItem) -> PlanItem:
    issue_codes = _issue_codes(item)
    blocking = any(issue.blocking for issue in item.issues)
    selected = bool(item.checked or item.selected) and not blocking
    action = item.operation or item.action
    selection_locked = blocking or action not in EXECUTABLE_ACTIONS
    selection_reason: str | None = None
    if blocking:
        selection_reason = "blocking"
    elif action not in EXECUTABLE_ACTIONS:
        selection_reason = "not_executable"
    elif item.sidecar_type and not selected:
        selection_reason = "sidecar_default_off"
    review_reasons = _review_reason_codes(item)
    buckets: set[str] = set()
    if selected:
        buckets.add("selected")
    if blocking:
        buckets.add("blocking")
    if any(not issue.blocking for issue in item.issues):
        buckets.add("warning")
    if item.requires_review:
        buckets.add("requires_review")
    if any(code in CONFLICT_CODES for code in issue_codes):
        buckets.add("conflict")
    if item.sidecar_type:
        buckets.add("sidecar")
    if action == Operation.QUARANTINE or action == "quarantine":
        buckets.add("junk_candidate")
    if item.manual_edited:
        buckets.add("manual_edited")
    if not buckets or (not blocking and not item.requires_review and not item.issues):
        buckets.add("ok")
    return item.model_copy(
        update={
            "checked": selected,
            "selected": selected,
            "blocking": blocking,
            "warning_count": len([issue for issue in item.issues if not issue.blocking]),
            "issue_codes": issue_codes,
            "review_reason_codes": review_reasons,
            "selection_locked": selection_locked,
            "selection_reason": selection_reason,
            "review_buckets": sorted(buckets),
        }
    )


def decorate_plan_items(items: list[PlanItem]) -> list[PlanItem]:
    return [decorate_plan_item(item) for item in items]


def summarize_plan(items: list[PlanItem]) -> dict[str, int]:
    items = decorate_plan_items(items)
    summary = Counter(str(item.action) for item in items)
    blocking = sum(1 for item in items if item.blocking)
    warning = sum(1 for item in items if item.warning_count)
    selected = sum(1 for item in items if item.selected)
    conflict = sum(1 for item in items if "conflict" in item.review_buckets)
    summary["blocking"] = blocking
    summary["warning"] = warning
    summary["selected"] = selected
    summary["total_items"] = len(items)
    summary["rename_items"] = sum(1 for item in items if item.action == Operation.RENAME or item.action == "rename")
    summary["quarantine_items"] = sum(1 for item in items if item.action == Operation.QUARANTINE or item.action == "quarantine")
    summary["sidecar_items"] = sum(1 for item in items if item.sidecar_type)
    summary["selected_items"] = selected
    summary["blocking_items"] = blocking
    summary["warning_items"] = warning
    summary["requires_review_items"] = sum(1 for item in items if item.requires_review)
    summary["manual_edited_items"] = sum(1 for item in items if item.manual_edited)
    summary["conflict_items"] = conflict
    summary["safe_selectable_items"] = sum(1 for item in items if _is_safe_selectable(item))
    return dict(summary)


def _target_for(root: Path, item: ScanItem, target_name: str) -> tuple[str, str]:
    source = Path(item.path)
    target = source.with_name(target_name)
    try:
        rel = str(target.resolve(strict=False).relative_to(root.resolve(strict=False)))
    except ValueError:
        rel = target.name
    return str(target), rel


def plan_item_from_scan(plan_id: str, root: Path, item: ScanItem, rules: RuleConfig) -> PlanItem:
    action = Operation.KEEP
    confidence = 1.0
    reason = "kept"
    target_name = item.name
    target_path = item.path
    target_rel_path = item.relative_path
    media_code = ""
    part_suffix = ""
    variant = ""
    removed_tokens: list[str] = []
    warnings: list[str] = []
    checked = False
    requires_review = False
    trace: list[RuleTraceStep] = []
    language_suffix = ""
    group_id = ""
    sidecar_type = classify_sidecar_type(item.extension)
    associated_media_code = ""
    sidecar_role = sidecar_type or ""
    ruleset_hash = compute_ruleset_hash(rules)

    junk, junk_reason = is_junk_file(item, rules.custom_junk_keywords, rules.trash_zero_byte)
    if junk:
        action = Operation.QUARANTINE
        confidence = 0.96
        reason = junk_reason
        checked = True
    elif item.kind == "media":
        suggestion = suggest_name_with_trace(item.name, rules)
        trace = suggestion.trace
        warnings = suggestion.warnings
        requires_review = suggestion.requires_review
        if suggestion.media_code:
            target_name = suggestion.suggested_name
            target_path, target_rel_path = _target_for(root, item, target_name)
            media_code = suggestion.media_code
            part_suffix = suggestion.part_suffix
            variant = suggestion.variant
            language_suffix = suggestion.language_suffix
            group_id = group_id_for_media_code(media_code)
            removed_tokens = [token for step in trace for token in step.removed_tokens]
            confidence = suggestion.confidence
            if item.name == target_name:
                action = Operation.KEEP
                reason = "already_clean"
                checked = False
            else:
                action = Operation.RENAME
                reason = "detected_media_code"
                checked = not requires_review
        else:
            action = Operation.REVIEW
            confidence = suggestion.confidence
            reason = "media_code_not_detected"
            checked = False
            requires_review = True
            warnings = suggestion.warnings
    elif item.kind == "sidecar":
        suggestion = suggest_name_with_trace(item.name, rules)
        trace = suggestion.trace
        warnings = suggestion.warnings
        confidence = suggestion.confidence
        language_suffix = suggestion.language_suffix
        if suggestion.media_code:
            media_code = suggestion.media_code
            associated_media_code = suggestion.media_code
            part_suffix = suggestion.part_suffix
            variant = suggestion.variant
            group_id = group_id_for_media_code(suggestion.media_code)
            target_name = suggestion.suggested_name
            target_path, target_rel_path = _target_for(root, item, target_name)
            removed_tokens = [token for step in trace for token in step.removed_tokens]
            if item.name == target_name:
                action = Operation.KEEP
                reason = "sidecar_already_clean"
            else:
                action = Operation.RENAME
                reason = "sidecar_suggested_rename"
        else:
            reason = "sidecar_unmatched"
            warnings = suggestion.warnings
        checked = False
        requires_review = False

    plan_item_id = hashlib.sha1(f"{plan_id}:{item.id}:{item.relative_path}".encode("utf-8", errors="ignore")).hexdigest()[:20]
    return PlanItem(
        id=plan_item_id,
        plan_id=plan_id,
        scan_item_id=item.id,
        source_path=item.path,
        source_rel_path=item.relative_path,
        original_name=item.name,
        target_name=target_name,
        suggested_name=target_name,
        target_path=target_path,
        target_rel_path=target_rel_path,
        action=action,
        operation=action,
        source=SuggestionSource.RULE,
        suggestion_source=SuggestionSource.RULE,
        confidence=confidence,
        reason=reason,
        warnings=warnings,
        checked=checked,
        selected_default=checked,
        requires_review=requires_review,
        relative_path=item.relative_path,
        extension=item.extension,
        size=item.size,
        mtime=item.mtime,
        media_code=media_code,
        part_suffix=part_suffix,
        variant=variant,
        language_suffix=language_suffix,
        group_id=group_id,
        sidecar_type=sidecar_type,  # type: ignore[arg-type]
        associated_media_code=associated_media_code,
        sidecar_role=sidecar_role,
        ruleset_hash=ruleset_hash,
        removed_tokens=removed_tokens,
        snapshot=item.snapshot,
        trace=trace,
    )


def create_plan(request: PlanRequest) -> PlanRecord:
    if request.scan_id:
        scan = get_scan(request.scan_id)
    elif request.files and request.root_path:
        scan = type("LegacyScan", (), {"scan_id": "", "root_path": request.root_path, "files": request.files})()
    else:
        raise ValueError("scan_id_required")

    plan_id = new_id("plan")
    root = Path(scan.root_path).resolve(strict=False)
    items = [
        plan_item_from_scan(plan_id, root, item, request.rules)
        for item in scan.files
    ]
    items = decorate_plan_items(validate_plan_items(root, items))
    plan_hash = compute_plan_hash(items)
    state = PlanState.VALIDATED if not any(issue.blocking for item in items for issue in item.issues) else PlanState.DRAFT
    record = PlanRecord(
        plan_id=plan_id,
        scan_id=scan.scan_id,
        root_path=scan.root_path,
        state=state,
        plan_hash=plan_hash,
        summary=summarize_plan(items),
        items=items,
    )
    if scan.scan_id:
        return save_plan(record, request.rules.model_dump(mode="json"))
    return record


def response_from_record(record: PlanRecord) -> PlanResponse:
    items = decorate_plan_items(record.items)
    return PlanResponse(
        plan_id=record.plan_id,
        scan_id=record.scan_id,
        plan_hash=record.plan_hash,
        root_path=record.root_path,
        items=items,
        summary=summarize_plan(items),
        state=record.state,
    )


def validate_stored_plan(plan_id: str) -> PlanRecord:
    record = get_plan(plan_id)
    items = decorate_plan_items(validate_plan_items(record.root_path, record.items))
    plan_hash = compute_plan_hash(items)
    state = PlanState.VALIDATED if not any(issue.blocking for item in items for issue in item.issues) else PlanState.STALE
    updated = record.model_copy(update={"items": items, "plan_hash": plan_hash, "state": state, "summary": summarize_plan(items)})
    return save_plan(updated)


def _assert_manual_target_name(target_name: str, original_extension: str) -> str:
    clean = target_name.strip()
    if not clean or clean in {".", ".."}:
        raise AppError(IssueCode.INVALID_TARGET_NAME, 400)
    if "/" in clean or "\\" in clean:
        raise AppError(IssueCode.PATH_SEPARATOR_IN_TARGET, 400)
    if Path(clean).suffix.lower() != original_extension.lower():
        raise AppError(IssueCode.EXTENSION_CHANGED, 400)
    filename_issues = validate_filename(clean, original_extension)
    if any(issue.blocking for issue in filename_issues):
        first = next(issue for issue in filename_issues if issue.blocking)
        if first.code == IssueCode.EXTENSION_CHANGED:
            raise AppError(IssueCode.EXTENSION_CHANGED, 400)
        raise AppError(IssueCode.INVALID_TARGET_NAME, 400)
    return clean


def patch_plan_item(plan_id: str, item_id: str, target_name: str) -> PlanItemPatchResponse:
    record = get_plan(plan_id)
    updated_items: list[PlanItem] = []
    edited_item: PlanItem | None = None
    now = utc_now_iso()
    for item in record.items:
        if item.id != item_id:
            updated_items.append(item)
            continue
        target_name = _assert_manual_target_name(target_name, item.extension)
        source = Path(item.source_path)
        target = source.with_name(target_name)
        try:
            target_rel = str(target.resolve(strict=False).relative_to(Path(record.root_path).resolve(strict=False)))
        except ValueError:
            target_rel = target.name
        edited_item = item.model_copy(
            update={
                "target_name": target_name,
                "suggested_name": target_name,
                "target_path": str(target),
                "target_rel_path": target_rel,
                "source": SuggestionSource.MANUAL,
                "suggestion_source": SuggestionSource.MANUAL,
                "action": Operation.RENAME,
                "operation": Operation.RENAME,
                "checked": True,
                "selected": True,
                "selected_default": True,
                "manual_edited": True,
                "last_edited_at": now,
                "trace": [
                    *item.trace,
                    RuleTraceStep(
                        rule_id="manual_edit",
                        before=item.target_name or item.suggested_name,
                        after=target_name,
                        preserved_tokens=[Path(target_name).suffix],
                    ),
                ],
            }
        )
        updated_items.append(edited_item)
    if edited_item is None:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 404)
    updated_items = decorate_plan_items(validate_plan_items(record.root_path, updated_items))
    plan_hash = compute_plan_hash(updated_items)
    state = PlanState.VALIDATED if not any(issue.blocking for item in updated_items for issue in item.issues) else PlanState.STALE
    saved = save_plan(record.model_copy(update={"items": updated_items, "plan_hash": plan_hash, "state": state, "summary": summarize_plan(updated_items)}))
    mark_llm_suggestions_stale(plan_id, item_id)
    affected = [
        item
        for item in saved.items
        if item.id == item_id or item.target_path.lower() == edited_item.target_path.lower()
    ]
    return PlanItemPatchResponse(
        plan_id=saved.plan_id,
        plan_hash=saved.plan_hash,
        item=next(item for item in saved.items if item.id == item_id),
        affected_items=affected,
        summary=saved.summary,
    )


def update_plan_selection(plan_id: str, request: PlanSelectionRequest) -> PlanSelectionResponse:
    record = get_plan(plan_id)
    current = {item.id for item in record.items if item.selected}
    known_ids = {item.id for item in record.items}
    requested = set(request.selected_item_ids)
    unknown = requested - known_ids
    if unknown:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 400)

    decorated = decorate_plan_items(record.items)
    by_id = {item.id: item for item in decorated}
    if request.mode == "select_safe":
        next_selected = {item.id for item in decorated if _is_safe_selectable(item)}
    elif request.mode == "replace":
        next_selected = requested
    elif request.mode == "add":
        next_selected = current | requested
    else:
        next_selected = current - requested

    locked = [item_id for item_id in next_selected if by_id[item_id].blocking or by_id[item_id].selection_locked]
    if locked:
        raise AppError(IssueCode.BLOCKING_ITEM_SELECTED, 400)

    updated_items = [
        decorate_plan_item(item.model_copy(update={"checked": item.id in next_selected, "selected": item.id in next_selected}))
        for item in decorated
    ]
    plan_hash = compute_plan_hash(updated_items)
    saved = save_plan(record.model_copy(update={"items": updated_items, "plan_hash": plan_hash, "summary": summarize_plan(updated_items)}))
    selected_ids = [item.id for item in saved.items if item.selected]
    return PlanSelectionResponse(
        plan_id=saved.plan_id,
        plan_hash=saved.plan_hash,
        summary=saved.summary,
        selected_item_ids=selected_ids,
        items=decorate_plan_items(saved.items),
    )


def build_execution_summary(plan_id: str, request: ExecutionSummaryRequest) -> ExecutionSummaryResponse:
    record = get_plan(plan_id)
    if request.plan_hash != record.plan_hash:
        raise AppError(IssueCode.PLAN_HASH_MISMATCH, 409)
    known_ids = {item.id for item in record.items}
    requested = set(request.selected_item_ids)
    if requested - known_ids:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 400)
    selected = decorate_plan_items([item for item in record.items if item.id in requested])
    blocking_count = sum(1 for item in selected if item.blocking)
    warning_count = sum(1 for item in selected if item.warning_count)
    requires_review_count = sum(1 for item in selected if item.requires_review)
    messages: list[str] = []
    if not selected:
        messages.append(str(IssueCode.NO_SELECTED_ITEMS))
    if blocking_count:
        messages.append(str(IssueCode.BLOCKING_ITEM_SELECTED))
    return ExecutionSummaryResponse(
        ok_to_execute=bool(selected) and blocking_count == 0,
        plan_id=record.plan_id,
        plan_hash=record.plan_hash,
        selected_count=len(selected),
        rename_count=sum(1 for item in selected if item.action == Operation.RENAME or item.action == "rename"),
        quarantine_count=sum(1 for item in selected if item.action == Operation.QUARANTINE or item.action == "quarantine"),
        sidecar_count=sum(1 for item in selected if item.sidecar_type),
        blocking_count=blocking_count,
        warning_count=warning_count,
        requires_review_count=requires_review_count,
        messages=messages,
    )


def export_plan_json(plan_id: str) -> dict:
    record = get_plan(plan_id)
    items = decorate_plan_items(record.items)
    return {
        "plan_id": record.plan_id,
        "plan_hash": record.plan_hash,
        "created_at": record.created_at,
        "ruleset_hash": items[0].ruleset_hash if items else "",
        "summary": summarize_plan(items),
        "items": [
            {
                "item_id": item.id,
                "operation": str(item.operation or item.action),
                "selected": item.selected,
                "original_name": item.original_name,
                "suggested_name": item.target_name or item.suggested_name,
                "target_name": item.target_name,
                "media_code": item.media_code,
                "part_suffix": item.part_suffix,
                "variant": item.variant,
                "language_suffix": item.language_suffix,
                "sidecar_type": item.sidecar_type,
                "group_id": item.group_id,
                "issue_codes": item.issue_codes,
                "confidence": item.confidence,
                "requires_review": item.requires_review,
                "manual_edited": item.manual_edited,
                "trace": [step.model_dump(mode="json") for step in item.trace],
            }
            for item in items
        ],
    }


def export_plan_csv(plan_id: str) -> str:
    record = get_plan(plan_id)
    items = decorate_plan_items(record.items)
    output = io.StringIO()
    fields = [
        "item_id",
        "operation",
        "selected",
        "status",
        "original_name",
        "suggested_name",
        "media_code",
        "part_suffix",
        "variant",
        "language_suffix",
        "sidecar_type",
        "group_id",
        "issue_codes",
        "confidence",
        "requires_review",
        "manual_edited",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "item_id": item.id,
                "operation": str(item.operation or item.action),
                "selected": str(item.selected).lower(),
                "status": "blocking" if item.blocking else ("review" if item.requires_review else "ok"),
                "original_name": item.original_name,
                "suggested_name": item.target_name or item.suggested_name,
                "media_code": item.media_code,
                "part_suffix": item.part_suffix,
                "variant": item.variant,
                "language_suffix": item.language_suffix,
                "sidecar_type": item.sidecar_type or "",
                "group_id": item.group_id,
                "issue_codes": ";".join(item.issue_codes),
                "confidence": f"{item.confidence:.6f}",
                "requires_review": str(item.requires_review).lower(),
                "manual_edited": str(item.manual_edited).lower(),
            }
        )
    return output.getvalue()
