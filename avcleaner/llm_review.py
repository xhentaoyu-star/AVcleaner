from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from . import llm
from .database import dumps, utc_now_iso
from .enums import IssueCode, Operation, PlanState, SuggestionSource
from .errors import AppError
from .models import (
    LLMBatchResponse,
    LLMPayloadPreviewRequest,
    LLMPayloadPreviewResponse,
    LLMSuggestItem,
    LLMSuggestion,
    LLMSuggestionApplyRequest,
    LLMSuggestionApplyResponse,
    LLMSuggestionPayloadPreview,
    LLMSuggestionRecord,
    LLMSuggestionRejectRequest,
    LLMSuggestionRejectResponse,
    LLMSuggestionsListResponse,
    PlanItem,
    PlanLLMSuggestRequest,
    PlanLLMSuggestResponse,
    RuleTraceStep,
    ValidationIssue,
)
from .planner import compute_plan_hash, decorate_plan_items, summarize_plan
from .repository import (
    create_llm_suggestion,
    get_llm_cache,
    get_llm_suggestion,
    get_plan,
    list_llm_suggestions,
    mark_llm_suggestions_stale,
    new_id,
    save_llm_cache,
    save_plan,
    update_llm_suggestion_status,
)
from .settings_store import effective_llm_api_key, get_settings
from .validators import validate_filename, validate_plan_items

SCHEMA_VERSION = 1
PROMPT_VERSION = "plan-review-v1"
RECOVERABLE_BATCH_ERROR_CODES = {
    str(IssueCode.LLM_INVALID_JSON),
    str(IssueCode.LLM_MULTIPLE_JSON_OBJECTS),
    str(IssueCode.LLM_NO_JSON_OBJECT),
    str(IssueCode.LLM_SCHEMA_INVALID),
    str(IssueCode.LLM_MISSING_REQUIRED_FIELD),
    str(IssueCode.LLM_EXTRA_FIELD),
    str(IssueCode.LLM_WRONG_FIELD_TYPE),
    str(IssueCode.LLM_CONFIDENCE_OUT_OF_RANGE),
}

SCHEMA_ERROR_CODES = {
    str(IssueCode.LLM_SCHEMA_INVALID),
    str(IssueCode.LLM_INVALID_JSON),
    str(IssueCode.LLM_NO_JSON_OBJECT),
    str(IssueCode.LLM_MULTIPLE_JSON_OBJECTS),
    str(IssueCode.LLM_MISSING_REQUIRED_FIELD),
    str(IssueCode.LLM_EXTRA_FIELD),
    str(IssueCode.LLM_WRONG_FIELD_TYPE),
    str(IssueCode.LLM_CONFIDENCE_OUT_OF_RANGE),
}

SAFETY_ERROR_CODES = {
    str(IssueCode.LLM_SUGGESTION_INVALID),
    str(IssueCode.LLM_PATH_LIKE_SUGGESTION),
    str(IssueCode.LLM_EXTENSION_CHANGED),
    str(IssueCode.LLM_RESERVED_NAME),
    str(IssueCode.LLM_INVALID_WINDOWS_NAME),
    str(IssueCode.LLM_TARGET_CONFLICT),
    str(IssueCode.LLM_PAYLOAD_PRIVACY_VIOLATION),
    str(IssueCode.BLOCKING_SUGGESTION),
}


def _hash(value: object) -> str:
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def _chunks(values: list, size: int) -> list[list]:
    safe_size = max(1, size)
    return [values[index : index + safe_size] for index in range(0, len(values), safe_size)]


def _known_items(plan_id: str, item_ids: list[str]) -> tuple[object, list[PlanItem]]:
    record = get_plan(plan_id)
    by_id = {item.id: item for item in record.items}
    unknown = set(item_ids) - set(by_id)
    if unknown:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 400)
    return record, [by_id[item_id] for item_id in item_ids]


def _neighbors(record_items: list[PlanItem], item: PlanItem, include_neighbors: bool) -> list[str]:
    if not include_neighbors:
        return []
    source_dir = str(Path(item.source_rel_path or item.relative_path).parent)
    names = [
        other.original_name
        for other in record_items
        if other.id != item.id and str(Path(other.source_rel_path or other.relative_path).parent) == source_dir
    ]
    return names[:8]


def _payload_preview(item: PlanItem, record_items: list[PlanItem], include_neighbors: bool, sends_full_path: bool) -> LLMSuggestionPayloadPreview:
    return LLMSuggestionPayloadPreview(
        item_id=item.id,
        filename=item.original_name,
        extension=item.extension,
        neighbor_filenames=_neighbors(record_items, item, include_neighbors),
        rule_suggested_name=item.target_name or item.suggested_name,
        media_code=item.media_code or None,
        sidecar_type=item.sidecar_type,
        language_suffix=item.language_suffix,
        full_path_included=sends_full_path,
    )


def build_payload_preview(plan_id: str, request: LLMPayloadPreviewRequest) -> LLMPayloadPreviewResponse:
    record, items = _known_items(plan_id, request.item_ids)
    settings = get_settings()
    previews = [
        _payload_preview(item, record.items, request.include_neighbors, settings.llm.send_full_path)
        for item in items
    ]
    return LLMPayloadPreviewResponse(
        plan_id=record.plan_id,
        items=previews,
        full_path_included=settings.llm.send_full_path,
        provider=settings.llm.provider,
        model=settings.llm.model,
        privacy={
            "sends_full_path": settings.llm.send_full_path,
            "sends_filename": True,
            "sends_extension": True,
            "sends_neighbors": request.include_neighbors,
        },
    )


def _suggest_item_from_preview(item: PlanItem, preview: LLMSuggestionPayloadPreview, send_full_path: bool) -> LLMSuggestItem:
    return LLMSuggestItem(
        id=item.id,
        name=preview.filename,
        extension=preview.extension,
        adjacent_names=preview.neighbor_filenames,
        path=item.source_path if send_full_path else None,
        rule_suggested_name=preview.rule_suggested_name,
        media_code=preview.media_code,
        sidecar_type=preview.sidecar_type,
        language_suffix=preview.language_suffix,
    )


def _cache_key(provider: str, model: str, item: PlanItem, preview: LLMSuggestionPayloadPreview) -> tuple[str, str]:
    settings = get_settings()
    payload = {
        "provider": provider,
        "model": model,
        "compatibility_mode": str(llm.provider_mode(settings.llm.model_copy(update={"provider": provider, "model": model}))),
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "filename": preview.filename.lower(),
        "extension": preview.extension.lower(),
        "neighbors_hash": _hash(preview.neighbor_filenames),
        "ruleset_hash": item.ruleset_hash,
        "sidecar_type": preview.sidecar_type,
        "language_suffix": preview.language_suffix,
    }
    payload_hash = _hash(payload)
    return _hash({"cache": payload}), payload_hash


def _issues_for_suggestion(record, item: PlanItem, suggested_name: str) -> list[ValidationIssue]:
    issues = validate_filename(suggested_name, item.extension)
    if any(issue.blocking for issue in issues):
        return issues
    source = Path(item.source_path)
    try:
        target = source.with_name(suggested_name)
    except ValueError:
        return validate_filename(suggested_name, item.extension)
    try:
        target_rel = str(target.resolve(strict=False).relative_to(Path(record.root_path).resolve(strict=False)))
    except ValueError:
        target_rel = target.name
    updated_items = []
    for current in record.items:
        if current.id == item.id:
            updated_items.append(
                current.model_copy(
                    update={
                        "target_name": suggested_name,
                        "suggested_name": suggested_name,
                        "target_path": str(target),
                        "target_rel_path": target_rel,
                        "action": Operation.RENAME,
                        "operation": Operation.RENAME,
                    }
                )
            )
        else:
            updated_items.append(current)
    validated = validate_plan_items(record.root_path, updated_items)
    return next(current.issues for current in validated if current.id == item.id)


def _llm_issue_code_from_validation(issues: list[ValidationIssue]) -> str:
    codes = {str(issue.code) for issue in issues if issue.blocking}
    if str(IssueCode.PATH_SEPARATOR_IN_TARGET) in codes or str(IssueCode.ALTERNATE_DATA_STREAM) in codes:
        return str(IssueCode.LLM_PATH_LIKE_SUGGESTION)
    if str(IssueCode.EXTENSION_CHANGED) in codes:
        return str(IssueCode.LLM_EXTENSION_CHANGED)
    if str(IssueCode.RESERVED_NAME) in codes or str(IssueCode.RESERVED_NAME_WITH_EXTENSION) in codes:
        return str(IssueCode.LLM_RESERVED_NAME)
    if str(IssueCode.DUPLICATE_TARGET) in codes or str(IssueCode.TARGET_EXISTS) in codes:
        return str(IssueCode.LLM_TARGET_CONFLICT)
    if codes:
        return str(IssueCode.LLM_INVALID_WINDOWS_NAME)
    return str(IssueCode.LLM_SUGGESTION_INVALID)


def _llm_state_from_error_code(error_code: str) -> str:
    if error_code == str(IssueCode.LLM_NOT_CONFIGURED):
        return "not_configured"
    if error_code in SCHEMA_ERROR_CODES:
        return "schema_error"
    if error_code in SAFETY_ERROR_CODES:
        return "safety_error"
    return "provider_error"


def ai_preview_item_ids(record) -> list[str]:
    return [
        item.id
        for item in decorate_plan_items(record.items)
        if (item.operation or item.action) == Operation.RENAME
        and not item.blocking
        and not item.sidecar_type
        and not item.manual_edited
    ]


def _record_from_suggestion(record, item: PlanItem, settings, suggestion: LLMSuggestion, payload_hash: str) -> LLMSuggestionRecord:
    validation_issues = _issues_for_suggestion(record, item, suggestion.suggested_name)
    status = "invalid" if any(issue.blocking for issue in validation_issues) else "valid"
    warnings = list(suggestion.warnings)
    if status == "invalid":
        code = _llm_issue_code_from_validation(validation_issues)
        if code not in warnings:
            warnings.append(code)
    response_payload = suggestion.model_dump(mode="json")
    return LLMSuggestionRecord(
        suggestion_id=new_id("llmsug"),
        plan_id=record.plan_id,
        item_id=item.id,
        provider=settings.provider,
        model=settings.model,
        schema_version=SCHEMA_VERSION,
        suggested_name=suggestion.suggested_name,
        media_code=suggestion.media_code or None,
        part_suffix=suggestion.part_suffix,
        variant=suggestion.variant,
        language_suffix=suggestion.language_suffix,
        removed_tokens=suggestion.removed_tokens,
        confidence=suggestion.confidence,
        reason=suggestion.reason,
        warnings=warnings,
        validation_issues=validation_issues,
        status=status,
        created_at=utc_now_iso(),
        payload_hash=payload_hash,
        response_hash=_hash(response_payload),
        generated_plan_hash=record.plan_hash,
    )


def _failed_record_from_error(record, item: PlanItem, settings, payload_hash: str, error_code: str) -> LLMSuggestionRecord:
    fallback_name = item.target_name or item.suggested_name or item.original_name
    response_payload = {"item_id": item.id, "error_code": error_code}
    return LLMSuggestionRecord(
        suggestion_id=new_id("llmsug"),
        plan_id=record.plan_id,
        item_id=item.id,
        provider=settings.provider,
        model=settings.model,
        schema_version=SCHEMA_VERSION,
        suggested_name=fallback_name,
        media_code=item.media_code or None,
        part_suffix=item.part_suffix,
        variant=item.variant,
        language_suffix=item.language_suffix,
        removed_tokens=[],
        confidence=0.0,
        reason="LLM batch failed; kept the rule preview suggestion.",
        warnings=[error_code],
        validation_issues=[],
        status="invalid",
        created_at=utc_now_iso(),
        payload_hash=payload_hash,
        response_hash=_hash(response_payload),
        generated_plan_hash=record.plan_hash,
    )


async def _generate_uncached_suggestions_for_chunk(
    record,
    chunk: list[tuple[PlanItem, LLMSuggestionPayloadPreview, str, str]],
    settings,
    *,
    allow_partial_failures: bool,
) -> list[LLMSuggestionRecord]:
    request_items = [
        _suggest_item_from_preview(item, preview, settings.send_full_path)
        for item, preview, _cache_key_value, _payload_hash in chunk
    ]
    try:
        batch = await llm.suggest_with_llm(
            type("Request", (), {"items": request_items, "settings": settings})(),
            settings,
        )
    except llm.LLMResponseError as exc:
        error_code = str(exc.error_code)
        if not allow_partial_failures:
            raise AppError(error_code, 400, exc.sanitized_message) from exc
        if len(chunk) > 1 and error_code in RECOVERABLE_BATCH_ERROR_CODES:
            midpoint = max(1, len(chunk) // 2)
            return [
                *await _generate_uncached_suggestions_for_chunk(record, chunk[:midpoint], settings, allow_partial_failures=allow_partial_failures),
                *await _generate_uncached_suggestions_for_chunk(record, chunk[midpoint:], settings, allow_partial_failures=allow_partial_failures),
            ]
        return [
            create_llm_suggestion(_failed_record_from_error(record, item, settings, payload_hash, error_code))
            for item, _preview, _cache_key_value, payload_hash in chunk
        ]
    except ValueError:
        error_code = str(IssueCode.LLM_SCHEMA_INVALID)
        if not allow_partial_failures:
            raise AppError(IssueCode.LLM_SCHEMA_INVALID, 400) from None
        if len(chunk) > 1:
            midpoint = max(1, len(chunk) // 2)
            return [
                *await _generate_uncached_suggestions_for_chunk(record, chunk[:midpoint], settings, allow_partial_failures=allow_partial_failures),
                *await _generate_uncached_suggestions_for_chunk(record, chunk[midpoint:], settings, allow_partial_failures=allow_partial_failures),
            ]
        return [
            create_llm_suggestion(_failed_record_from_error(record, item, settings, payload_hash, error_code))
            for item, _preview, _cache_key_value, payload_hash in chunk
        ]
    except TimeoutError:
        error_code = str(IssueCode.LLM_TIMEOUT)
        if not allow_partial_failures:
            raise AppError(IssueCode.LLM_TIMEOUT, 504) from None
        return [
            create_llm_suggestion(_failed_record_from_error(record, item, settings, payload_hash, error_code))
            for item, _preview, _cache_key_value, payload_hash in chunk
        ]
    except Exception as exc:
        raise AppError(IssueCode.LLM_PROVIDER_ERROR, 502, "LLM provider error") from exc

    stored_suggestions: list[LLMSuggestionRecord] = []
    suggestions_by_item = {suggestion.item_id: suggestion for suggestion in batch.suggestions}
    for item, _preview, cache_key, payload_hash in chunk:
        llm_suggestion = suggestions_by_item.get(item.id)
        if llm_suggestion is None:
            stored_suggestions.append(
                create_llm_suggestion(
                    _failed_record_from_error(record, item, settings, payload_hash, str(IssueCode.LLM_SCHEMA_INVALID))
                )
            )
            continue
        stored = create_llm_suggestion(_record_from_suggestion(record, item, settings, llm_suggestion, payload_hash))
        if stored.status == "valid":
            save_llm_cache(cache_key, settings.provider, settings.model, SCHEMA_VERSION, payload_hash, llm_suggestion.model_dump(mode="json"))
        stored_suggestions.append(stored)
    return stored_suggestions


async def generate_llm_suggestions(plan_id: str, request: PlanLLMSuggestRequest) -> PlanLLMSuggestResponse:
    record, items = _known_items(plan_id, request.item_ids)
    app_settings = get_settings()
    settings = app_settings.llm.model_copy(update={"api_key": effective_llm_api_key(app_settings)})
    if settings.provider == "disabled" or not settings.model:
        raise AppError(IssueCode.LLM_NOT_CONFIGURED, 400)

    cache_hits = 0
    cache_misses = 0
    suggestions: list[LLMSuggestionRecord] = []
    uncached_items: list[tuple[PlanItem, LLMSuggestionPayloadPreview, str, str]] = []
    for item in items:
        preview = _payload_preview(item, record.items, request.include_neighbors, settings.send_full_path)
        if preview.full_path_included and not settings.send_full_path:
            raise AppError(IssueCode.LLM_PAYLOAD_PRIVACY_VIOLATION, 400)
        cache_key, payload_hash = _cache_key(settings.provider, settings.model, item, preview)
        cached = get_llm_cache(cache_key) if request.use_cache else None
        if cached:
            cache_hits += 1
            llm_suggestion = LLMSuggestion.model_validate(cached)
            stored = create_llm_suggestion(_record_from_suggestion(record, item, settings, llm_suggestion, payload_hash))
            suggestions.append(stored)
        else:
            cache_misses += 1
            uncached_items.append((item, preview, cache_key, payload_hash))

    for chunk in _chunks(uncached_items, max(1, settings.max_batch_size)):
        suggestions.extend(
            await _generate_uncached_suggestions_for_chunk(
                record,
                chunk,
                settings,
                allow_partial_failures=request.allow_partial_failures,
            )
        )
    return PlanLLMSuggestResponse(plan_id=record.plan_id, suggestions=suggestions, cache_hits=cache_hits, cache_misses=cache_misses)


def list_plan_llm_suggestions(plan_id: str) -> LLMSuggestionsListResponse:
    get_plan(plan_id)
    return LLMSuggestionsListResponse(plan_id=plan_id, suggestions=list_llm_suggestions(plan_id))


def _target_fields(record, item: PlanItem, suggested_name: str) -> tuple[str, str]:
    source = Path(item.source_path)
    target = source.with_name(suggested_name)
    try:
        target_rel = str(target.resolve(strict=False).relative_to(Path(record.root_path).resolve(strict=False)))
    except ValueError:
        target_rel = target.name
    return str(target), target_rel


def apply_llm_suggestions_to_preview(
    plan_id: str,
    suggestions: Iterable[LLMSuggestionRecord],
    *,
    requested_item_ids: Iterable[str],
    llm_mode: str = "",
) -> object:
    record = get_plan(plan_id)
    requested = list(dict.fromkeys(requested_item_ids))
    known_ids = {item.id for item in record.items}
    unknown = set(requested) - known_ids
    if unknown:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 400)

    suggestions_by_item = {suggestion.item_id: suggestion for suggestion in suggestions}
    updated_items = list(record.items)
    applied_count = 0
    invalid_count = 0
    fallback_count = 0

    for index, current in enumerate(list(updated_items)):
        if current.id not in requested:
            continue
        suggestion = suggestions_by_item.get(current.id)
        if current.manual_edited and (current.source == SuggestionSource.MANUAL or current.suggestion_source == SuggestionSource.MANUAL):
            fallback_count += 1
            updated_items[index] = current.model_copy(update={"llm_state": "valid_but_not_used"})
            continue
        if suggestion is None:
            invalid_count += 1
            fallback_count += 1
            updated_items[index] = current.model_copy(update={"llm_state": "schema_error", "llm_error_code": str(IssueCode.LLM_SCHEMA_INVALID)})
            continue
        validation_codes = list(dict.fromkeys(str(issue.code) for issue in suggestion.validation_issues))
        if suggestion.status != "valid":
            invalid_count += 1
            fallback_count += 1
            error_code = next((code for code in suggestion.warnings if str(code).startswith("llm_")), str(IssueCode.LLM_SUGGESTION_INVALID))
            updated_items[index] = current.model_copy(
                update={
                    "llm_state": _llm_state_from_error_code(error_code),
                    "llm_error_code": error_code,
                    "llm_suggested_name": suggestion.suggested_name,
                    "llm_confidence": suggestion.confidence,
                    "llm_reason": suggestion.reason,
                    "llm_warnings": suggestion.warnings,
                    "llm_validation_codes": validation_codes,
                }
            )
            continue

        working_record = record.model_copy(update={"items": updated_items})
        issues = _issues_for_suggestion(working_record, current, suggestion.suggested_name)
        if any(issue.blocking for issue in issues):
            invalid_count += 1
            fallback_count += 1
            error_code = _llm_issue_code_from_validation(issues)
            updated_items[index] = current.model_copy(
                update={
                    "llm_state": _llm_state_from_error_code(error_code),
                    "llm_error_code": error_code,
                    "llm_suggested_name": suggestion.suggested_name,
                    "llm_confidence": suggestion.confidence,
                    "llm_reason": suggestion.reason,
                    "llm_warnings": list(dict.fromkeys([*suggestion.warnings, error_code])),
                    "llm_validation_codes": list(dict.fromkeys(str(issue.code) for issue in issues)),
                }
            )
            continue

        target_path, target_rel = _target_fields(record, current, suggestion.suggested_name)
        applied_count += 1
        updated_items[index] = current.model_copy(
            update={
                "target_name": suggestion.suggested_name,
                "suggested_name": suggestion.suggested_name,
                "target_path": target_path,
                "target_rel_path": target_rel,
                "source": SuggestionSource.LLM,
                "suggestion_source": SuggestionSource.LLM,
                "llm_state": "applied_to_preview",
                "llm_error_code": "",
                "llm_suggested_name": suggestion.suggested_name,
                "llm_confidence": suggestion.confidence,
                "llm_reason": suggestion.reason,
                "llm_warnings": suggestion.warnings,
                "llm_validation_codes": validation_codes,
                "llm_accepted": False,
                "llm_suggestion_id": suggestion.suggestion_id,
                "trace": [
                    *current.trace,
                    RuleTraceStep(
                        rule_id="llm_preview",
                        before=current.target_name or current.suggested_name,
                        after=suggestion.suggested_name,
                        preserved_tokens=[Path(suggestion.suggested_name).suffix],
                        warnings=suggestion.warnings,
                    ),
                ],
            }
        )

    updated_items = decorate_plan_items(validate_plan_items(record.root_path, updated_items))
    plan_hash = compute_plan_hash(updated_items)
    state = PlanState.VALIDATED if not any(issue.blocking for item in updated_items for issue in item.issues) else PlanState.STALE
    return save_plan(
        record.model_copy(
            update={
                "items": updated_items,
                "plan_hash": plan_hash,
                "state": state,
                "summary": summarize_plan(updated_items),
                "preview_mode": "ai",
                "llm_used": True,
                "llm_mode": llm_mode,
                "llm_applied_count": applied_count,
                "llm_invalid_count": invalid_count,
                "llm_fallback_to_rule_count": fallback_count,
            }
        )
    )


def mark_ai_preview_fallback(plan_id: str, item_ids: Iterable[str], *, error_code: str, llm_mode: str = "") -> object:
    record = get_plan(plan_id)
    requested = set(item_ids)
    state_name = _llm_state_from_error_code(error_code)
    updated_items = [
        item.model_copy(update={"llm_state": state_name, "llm_error_code": error_code})
        if item.id in requested
        else item
        for item in record.items
    ]
    return save_plan(
        record.model_copy(
            update={
                "items": updated_items,
                "preview_mode": "ai",
                "llm_used": True,
                "llm_mode": llm_mode,
                "llm_applied_count": 0,
                "llm_invalid_count": len(requested),
                "llm_fallback_to_rule_count": len(requested),
                "messages": list(dict.fromkeys([*record.messages, "ai_preview_failed_fallback", str(error_code)])),
            }
        )
    )


def mark_ai_preview_no_eligible_items(plan_id: str, *, llm_mode: str = "") -> object:
    record = get_plan(plan_id)
    return save_plan(
        record.model_copy(
            update={
                "preview_mode": "ai",
                "llm_used": False,
                "llm_mode": llm_mode,
                "messages": list(dict.fromkeys([*record.messages, "ai_preview_no_eligible_items"])),
            }
        )
    )


def accept_llm_suggestion(plan_id: str, suggestion_id: str, request: LLMSuggestionApplyRequest) -> LLMSuggestionApplyResponse:
    record = get_plan(plan_id)
    suggestion = get_llm_suggestion(suggestion_id)
    if suggestion.plan_id != plan_id:
        raise AppError(IssueCode.SUGGESTION_PLAN_MISMATCH, 404)
    if request.expected_plan_hash != record.plan_hash:
        raise AppError(IssueCode.PLAN_HASH_MISMATCH, 409)
    if suggestion.status == "stale":
        raise AppError(IssueCode.SUGGESTION_STALE, 409)
    item = next((current for current in record.items if current.id == suggestion.item_id), None)
    if item is None:
        raise AppError(IssueCode.UNKNOWN_PLAN_ITEM, 400)
    if item.manual_edited and (item.source == SuggestionSource.MANUAL or item.suggestion_source == SuggestionSource.MANUAL):
        raise AppError(IssueCode.MANUAL_EDIT_CONFLICT, 409)
    issues = _issues_for_suggestion(record, item, suggestion.suggested_name)
    if any(issue.blocking for issue in issues):
        raise AppError(IssueCode.BLOCKING_SUGGESTION, 400)

    target_path, target_rel = _target_fields(record, item, suggestion.suggested_name)
    updated_items: list[PlanItem] = []
    now = utc_now_iso()
    for current in record.items:
        if current.id != item.id:
            updated_items.append(current)
            continue
        updated_items.append(
            current.model_copy(
                update={
                    "target_name": suggestion.suggested_name,
                    "suggested_name": suggestion.suggested_name,
                    "target_path": target_path,
                    "target_rel_path": target_rel,
                    "source": SuggestionSource.LLM,
                    "suggestion_source": SuggestionSource.LLM,
                    "action": Operation.RENAME,
                    "operation": Operation.RENAME,
                    "manual_edited": True,
                    "last_edited_at": now,
                    "llm_accepted": True,
                    "llm_suggestion_id": suggestion.suggestion_id,
                    "trace": [
                        *current.trace,
                        RuleTraceStep(
                            rule_id="llm_accept",
                            before=current.target_name or current.suggested_name,
                            after=suggestion.suggested_name,
                            preserved_tokens=[Path(suggestion.suggested_name).suffix],
                            warnings=suggestion.warnings,
                        ),
                    ],
                }
            )
        )
    updated_items = decorate_plan_items(validate_plan_items(record.root_path, updated_items))
    plan_hash = compute_plan_hash(updated_items)
    state = PlanState.VALIDATED if not any(issue.blocking for current in updated_items for issue in current.issues) else PlanState.STALE
    saved = save_plan(record.model_copy(update={"items": updated_items, "plan_hash": plan_hash, "state": state, "summary": summarize_plan(updated_items)}))
    accepted = update_llm_suggestion_status(suggestion_id, "accepted", accepted_at=now)
    mark_llm_suggestions_stale(plan_id, item.id, except_suggestion_id=suggestion_id)
    affected = [current for current in saved.items if current.id == item.id or current.target_path.lower() == target_path.lower()]
    return LLMSuggestionApplyResponse(
        plan_id=plan_id,
        plan_hash=saved.plan_hash,
        item=next(current for current in saved.items if current.id == item.id),
        affected_items=affected,
        summary=saved.summary,
        suggestion=accepted,
    )


def reject_llm_suggestion(plan_id: str, suggestion_id: str, _request: LLMSuggestionRejectRequest) -> LLMSuggestionRejectResponse:
    get_plan(plan_id)
    suggestion = get_llm_suggestion(suggestion_id)
    if suggestion.plan_id != plan_id:
        raise AppError(IssueCode.SUGGESTION_PLAN_MISMATCH, 404)
    rejected = update_llm_suggestion_status(suggestion_id, "rejected", rejected_at=utc_now_iso())
    return LLMSuggestionRejectResponse(plan_id=plan_id, suggestion=rejected)
