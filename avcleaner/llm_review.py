from __future__ import annotations

import hashlib
from pathlib import Path

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


def _hash(value: object) -> str:
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


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
    payload = {
        "provider": provider,
        "model": model,
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


def _record_from_suggestion(record, item: PlanItem, settings, suggestion: LLMSuggestion, payload_hash: str) -> LLMSuggestionRecord:
    validation_issues = _issues_for_suggestion(record, item, suggestion.suggested_name)
    status = "invalid" if any(issue.blocking for issue in validation_issues) else "valid"
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
        warnings=suggestion.warnings,
        validation_issues=validation_issues,
        status=status,
        created_at=utc_now_iso(),
        payload_hash=payload_hash,
        response_hash=_hash(response_payload),
        generated_plan_hash=record.plan_hash,
    )


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

    if uncached_items:
        request_items = [
            _suggest_item_from_preview(item, preview, settings.send_full_path)
            for item, preview, _cache_key_value, _payload_hash in uncached_items
        ]
        try:
            batch = await llm.suggest_with_llm(
                type("Request", (), {"items": request_items, "settings": settings})(),
                settings,
            )
        except ValueError as exc:
            raise AppError(IssueCode.LLM_SCHEMA_INVALID, 400) from exc
        except TimeoutError as exc:
            raise AppError(IssueCode.LLM_TIMEOUT, 504) from exc
        except Exception as exc:
            raise AppError(IssueCode.LLM_PROVIDER_ERROR, 502, "LLM provider error") from exc
        suggestions_by_item = {suggestion.item_id: suggestion for suggestion in batch.suggestions}
        for item, _preview, cache_key, payload_hash in uncached_items:
            llm_suggestion = suggestions_by_item.get(item.id)
            if llm_suggestion is None:
                raise AppError(IssueCode.LLM_SCHEMA_INVALID, 400)
            stored = create_llm_suggestion(_record_from_suggestion(record, item, settings, llm_suggestion, payload_hash))
            if stored.status == "valid":
                save_llm_cache(cache_key, settings.provider, settings.model, SCHEMA_VERSION, payload_hash, llm_suggestion.model_dump(mode="json"))
            suggestions.append(stored)
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
