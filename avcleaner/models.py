from __future__ import annotations

import string
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from .constants import JUNK_EXTENSIONS, RULE_TRACE_IDS, SIDECAR_EXTENSIONS, VIDEO_EXTENSIONS
from .enums import IssueCode, IssueSeverity, Operation, PlanState, RunItemState, RunState, SuggestionSource


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _settings_error(code: str) -> PydanticCustomError:
    return PydanticCustomError(code, code, {"error_code": code})


def _default_enabled_rules() -> dict[str, bool]:
    return {rule_id: True for rule_id in sorted(RULE_TRACE_IDS)}


def _default_sidecar_extensions() -> dict[str, list[str]]:
    return {
        "subtitle": [".ass", ".srt", ".ssa", ".vtt"],
        "image": [".jpeg", ".jpg", ".png", ".webp"],
        "nfo": [".nfo"],
    }


def _validate_extension_list(values: list[str], *, allow_empty: bool = False) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value and allow_empty:
            continue
        if not value.startswith(".") or not value[1:] or any(char in value for char in "\\/:*?\"<>|\x00"):
            raise _settings_error("rule_settings_invalid_extension")
        normalized = value.lower()
        if normalized in seen:
            raise _settings_error("rule_settings_duplicate_extension")
        seen.add(normalized)
        result.append(normalized)
    return sorted(result)


def _validate_output_template(value: str) -> str:
    allowed = {"code", "part", "variant", "language", "ext"}
    try:
        fields = [field_name for _, field_name, _, _ in string.Formatter().parse(value) if field_name]
    except ValueError as exc:
        raise _settings_error("rule_settings_invalid_template") from exc
    if not fields or "code" not in fields or any(field not in allowed for field in fields):
        raise _settings_error("rule_settings_invalid_template")
    if any(char in value for char in "\\/:*?\"<>|\x00"):
        raise _settings_error("rule_settings_invalid_template")
    return value


class RuleSettings(StrictModel):
    ruleset_version: int = 1
    enabled_rules: dict[str, bool] = Field(default_factory=_default_enabled_rules)
    output_template: str = "{code}{part}{variant}{language}{ext}"
    media_code_style: Literal["standard", "preserve_existing"] = "standard"
    fc2_style: Literal["FC2PPV-1234567"] = "FC2PPV-1234567"
    preserve_extension: bool = True
    preserve_part_suffix: bool = True
    preserve_variant: bool = True
    preserve_sidecar_language: bool = True
    remove_ad_domains: list[str] = Field(default_factory=list)
    remove_bracket_ads: bool = True
    remove_noise_tokens: list[str] = Field(default_factory=list)
    video_extensions: list[str] = Field(default_factory=lambda: sorted(VIDEO_EXTENSIONS))
    sidecar_extensions: dict[str, list[str]] = Field(default_factory=_default_sidecar_extensions)
    junk_extensions: list[str] = Field(default_factory=lambda: sorted(JUNK_EXTENSIONS))
    review_threshold: float = 0.7
    max_filename_length: int = 255
    normalize_case: bool = True
    keep_part_suffix: bool = True
    trash_zero_byte: bool = True
    custom_remove_tokens: list[str] = Field(default_factory=list)
    custom_junk_keywords: list[str] = Field(default_factory=list)

    @field_validator("enabled_rules", mode="before")
    @classmethod
    def normalize_enabled_rules(cls, value: dict[str, bool] | None) -> dict[str, bool]:
        result = _default_enabled_rules()
        if value is None:
            return result
        unknown = set(value) - RULE_TRACE_IDS
        if unknown:
            raise _settings_error("rule_settings_unknown_rule")
        result.update({key: bool(enabled) for key, enabled in value.items()})
        return result

    @field_validator("output_template")
    @classmethod
    def validate_output_template(cls, value: str) -> str:
        return _validate_output_template(value)

    @field_validator("video_extensions", "junk_extensions")
    @classmethod
    def validate_extensions(cls, values: list[str]) -> list[str]:
        return _validate_extension_list(values)

    @field_validator("sidecar_extensions")
    @classmethod
    def validate_sidecar_extensions(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        allowed_keys = {"subtitle", "image", "nfo", "other"}
        if set(values) - allowed_keys:
            raise _settings_error("rule_settings_invalid_extension")
        seen: set[str] = set()
        result: dict[str, list[str]] = {}
        for key, exts in values.items():
            normalized = _validate_extension_list(exts)
            for ext in normalized:
                if ext in seen:
                    raise _settings_error("rule_settings_duplicate_extension")
                seen.add(ext)
            result[key] = normalized
        return result

    @field_validator("remove_ad_domains")
    @classmethod
    def validate_ad_domains(cls, values: list[str]) -> list[str]:
        result = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip().lower()
            if not value:
                continue
            if any(char in value for char in "\\/\x00") or any(ord(char) < 32 for char in value):
                raise _settings_error("rule_settings_invalid_ad_domain")
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result

    @field_validator("remove_noise_tokens", "custom_remove_tokens")
    @classmethod
    def normalize_token_list(cls, values: list[str]) -> list[str]:
        result = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if not value:
                continue
            key = value.lower()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @field_validator("review_threshold")
    @classmethod
    def validate_review_threshold(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise _settings_error("rule_settings_invalid_review_threshold")
        return value

    @field_validator("max_filename_length")
    @classmethod
    def validate_max_filename_length(cls, value: int) -> int:
        if value < 64 or value > 255:
            raise _settings_error("rule_settings_invalid_max_filename_length")
        return value

    @model_validator(mode="after")
    def validate_sidecar_language_policy(self) -> "RuleSettings":
        if not self.preserve_sidecar_language:
            raise _settings_error("rule_settings_sidecar_language_required")
        return self


RuleConfig = RuleSettings


class RenameConfig(StrictModel):
    template: str = "{code}{part}{variant}{ext}"
    auto_cd_conflict: bool = False
    block_extension_change: bool = True


class FilesystemConfig(StrictModel):
    long_path_mode: Literal["conservative", "long_path_aware"] = "conservative"


class LLMSettings(StrictModel):
    provider: Literal["disabled", "openai_compatible", "ollama"] = "disabled"
    compatibility_mode: Literal["openai_strict_json_schema", "prompt_json_compat", "claude_gateway_compat", "ollama_format_json"] = (
        "openai_strict_json_schema"
    )
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.0
    max_batch_size: int = 20
    max_concurrency: int = 2
    send_full_path: bool = False
    min_confidence: float = 0.7


class AppSettings(StrictModel):
    schema_version: int = 3
    first_run_seen: bool = False
    video_extensions: list[str] = Field(default_factory=lambda: sorted(VIDEO_EXTENSIONS))
    sidecar_extensions: list[str] = Field(default_factory=lambda: sorted(SIDECAR_EXTENSIONS))
    exclude_dirs: list[str] = Field(default_factory=list)
    rules: RuleConfig = Field(default_factory=RuleConfig)
    rename: RenameConfig = Field(default_factory=RenameConfig)
    filesystem: FilesystemConfig = Field(default_factory=FilesystemConfig)
    llm: LLMSettings = Field(default_factory=LLMSettings)

    @field_validator("video_extensions", "sidecar_extensions")
    @classmethod
    def normalize_extensions(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            ext = value.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            result.append(ext)
        return sorted(set(result))


class FileSnapshot(StrictModel):
    size: int
    created_ns: int
    modified_ns: int
    fingerprint: str


class ScanRequest(StrictModel):
    root_path: str
    recursive: bool = True
    include_hidden: bool = False
    extensions: list[str] | None = None
    exclude_dirs: list[str] | None = None


class ScanItem(StrictModel):
    id: str
    scan_id: str = ""
    path: str
    relative_path: str
    name: str
    stem: str
    extension: str
    size: int
    mtime: float
    kind: Literal["media", "sidecar", "junk", "other"]
    snapshot: FileSnapshot | None = None
    is_hidden: bool = False


FileItem = ScanItem


class ScanResponse(StrictModel):
    scan_id: str = ""
    root_path: str
    files: list[ScanItem]
    total_files: int
    skipped_dirs: list[str] = Field(default_factory=list)


class ValidationIssue(StrictModel):
    code: IssueCode
    severity: IssueSeverity
    blocking: bool = False
    message_key: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class RuleTraceStep(StrictModel):
    rule_id: str
    before: str = ""
    after: str = ""
    removed_tokens: list[str] = Field(default_factory=list)
    preserved_tokens: list[str] = Field(default_factory=list)
    confidence_delta: float | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_removed(cls, data: Any) -> Any:
        if isinstance(data, dict) and "removed" in data and "removed_tokens" not in data:
            data = dict(data)
            data["removed_tokens"] = data.pop("removed")
            data.pop("details", None)
        return data


TraceStep = RuleTraceStep


class RuleSuggestion(StrictModel):
    original_name: str
    suggested_name: str
    media_code: str | None = None
    part_suffix: str = ""
    variant: str = ""
    language_suffix: str = ""
    sidecar_type: Literal["subtitle", "image", "nfo", "other"] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    trace: list[RuleTraceStep]
    warnings: list[str] = Field(default_factory=list)
    requires_review: bool = False


class SidecarInfo(StrictModel):
    item_id: str
    rel_path: str
    filename: str
    extension: str
    sidecar_type: Literal["subtitle", "image", "nfo", "other"] | None = None
    associated_media_code: str | None = None
    language_suffix: str = ""
    sidecar_role: str | None = None
    default_selected: bool = False
    warnings: list[str] = Field(default_factory=list)


class PlanItem(StrictModel):
    id: str
    plan_id: str = ""
    scan_item_id: str = ""
    source_path: str
    source_rel_path: str = ""
    original_name: str
    target_name: str = ""
    suggested_name: str
    target_path: str
    target_rel_path: str = ""
    action: Operation
    operation: Operation | None = None
    source: SuggestionSource
    suggestion_source: SuggestionSource | None = None
    confidence: float = 0.0
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    checked: bool = True
    selected: bool = True
    selected_default: bool = True
    selection_locked: bool = False
    selection_reason: str | None = None
    requires_review: bool = False
    review_reason_codes: list[str] = Field(default_factory=list)
    requires_two_step: bool = False
    temp_target_name: str = ""
    blocking: bool = False
    warning_count: int = 0
    issue_codes: list[str] = Field(default_factory=list)
    review_buckets: list[str] = Field(default_factory=list)
    manual_edited: bool = False
    last_edited_at: str | None = None
    llm_accepted: bool = False
    llm_suggestion_id: str = ""
    relative_path: str = ""
    extension: str = ""
    size: int = 0
    mtime: float = 0.0
    media_code: str = ""
    part_suffix: str = ""
    variant: str = ""
    language_suffix: str = ""
    group_id: str = ""
    sidecar_type: Literal["subtitle", "image", "nfo", "other"] | None = None
    associated_media_code: str = ""
    sidecar_role: str = ""
    ruleset_hash: str = ""
    removed_tokens: list[str] = Field(default_factory=list)
    snapshot: FileSnapshot | None = None
    trace: list[RuleTraceStep] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.operation is None:
            self.operation = self.action
        if self.suggestion_source is None:
            self.suggestion_source = self.source
        if not self.target_name:
            self.target_name = self.suggested_name
        if not self.relative_path:
            self.relative_path = self.source_rel_path
        if not self.source_rel_path:
            self.source_rel_path = self.relative_path
        blocking = any(issue.blocking for issue in self.issues)
        self.checked = self.checked and not blocking
        self.selected = self.checked
        self.blocking = blocking
        self.warning_count = len([issue for issue in self.issues if not issue.blocking])
        self.issue_codes = [str(issue.code) for issue in self.issues]


class PlanRecord(StrictModel):
    plan_id: str
    scan_id: str
    root_path: str
    state: PlanState = PlanState.DRAFT
    plan_hash: str
    summary: dict[str, int] = Field(default_factory=dict)
    items: list[PlanItem] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class PlanRequest(StrictModel):
    scan_id: str | None = None
    root_path: str | None = None
    files: list[ScanItem] | None = None
    rules: RuleConfig = Field(default_factory=RuleConfig)
    use_llm: bool = False


class PlanResponse(StrictModel):
    plan_id: str = ""
    scan_id: str = ""
    plan_hash: str = ""
    root_path: str
    items: list[PlanItem]
    summary: dict[str, int]
    state: PlanState = PlanState.DRAFT


class PlanExecuteRequest(StrictModel):
    selected_item_ids: list[str]
    confirm: bool = False
    plan_hash: str


class PlanItemPatchRequest(StrictModel):
    target_name: str


class PlanItemPatchResponse(StrictModel):
    plan_id: str
    plan_hash: str
    item: PlanItem
    affected_items: list[PlanItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class PlanSelectionRequest(StrictModel):
    selected_item_ids: list[str] = Field(default_factory=list)
    mode: Literal["replace", "add", "remove", "select_safe"] = "replace"


class PlanSelectionResponse(StrictModel):
    plan_id: str
    plan_hash: str
    summary: dict[str, int]
    selected_item_ids: list[str]
    items: list[PlanItem] = Field(default_factory=list)


class ExecutionSummaryRequest(StrictModel):
    selected_item_ids: list[str]
    plan_hash: str


class ExecutionSummaryResponse(StrictModel):
    ok_to_execute: bool
    plan_id: str
    plan_hash: str
    selected_count: int
    rename_count: int
    quarantine_count: int
    sidecar_count: int
    blocking_count: int
    warning_count: int
    requires_review_count: int
    messages: list[str] = Field(default_factory=list)


class LLMSuggestion(StrictModel):
    item_id: str
    suggested_name: str
    media_code: str = ""
    part_suffix: str = ""
    variant: str = ""
    language_suffix: str = ""
    removed_tokens: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)


class LLMBatchResponse(StrictModel):
    suggestions: list[LLMSuggestion]


class LLMSuggestItem(StrictModel):
    id: str
    name: str
    extension: str
    adjacent_names: list[str] = Field(default_factory=list)
    path: str | None = None
    rule_suggested_name: str | None = None
    media_code: str | None = None
    sidecar_type: str | None = None
    language_suffix: str = ""


class LLMSuggestRequest(StrictModel):
    items: list[LLMSuggestItem]
    settings: LLMSettings | None = None


class LLMTestRequest(StrictModel):
    settings: LLMSettings | None = None


class LLMTestResponse(StrictModel):
    ok: bool
    provider: str
    model: str
    compatibility_mode: str = ""
    used_response_format_json_schema: bool = False
    json_extracted: bool = False
    stage: str = ""
    field_path: str = ""
    safety_valid: bool = False
    latency_ms: int = 0
    schema_valid: bool = False
    payload_preview: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    sanitized_message: str = ""


class LLMSuggestionPayloadPreview(StrictModel):
    item_id: str
    filename: str
    extension: str
    neighbor_filenames: list[str] = Field(default_factory=list)
    rule_suggested_name: str | None = None
    media_code: str | None = None
    sidecar_type: str | None = None
    language_suffix: str = ""
    full_path_included: bool = False


class LLMPayloadPreviewRequest(StrictModel):
    item_ids: list[str]
    include_neighbors: bool = True


class LLMPayloadPreviewResponse(StrictModel):
    plan_id: str
    items: list[LLMSuggestionPayloadPreview]
    full_path_included: bool = False
    provider: str = ""
    model: str = ""
    privacy: dict[str, bool] = Field(default_factory=dict)


class PlanLLMSuggestRequest(StrictModel):
    item_ids: list[str]
    include_neighbors: bool = True
    use_cache: bool = True


class LLMSuggestionRequest(StrictModel):
    plan_id: str
    item_ids: list[str]
    mode: Literal["selected", "requires_review", "explicit"] = "explicit"
    include_neighbors: bool = True
    dry_run: bool = False


class LLMSuggestionRecord(StrictModel):
    suggestion_id: str
    plan_id: str
    item_id: str
    provider: str
    model: str
    schema_version: int = 1
    suggested_name: str
    media_code: str | None = None
    part_suffix: str = ""
    variant: str = ""
    language_suffix: str = ""
    removed_tokens: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    status: Literal["pending", "valid", "invalid", "accepted", "rejected", "stale"] = "pending"
    created_at: str
    payload_hash: str
    response_hash: str
    generated_plan_hash: str = ""
    accepted_at: str = ""
    rejected_at: str = ""


class PlanLLMSuggestResponse(StrictModel):
    plan_id: str
    suggestions: list[LLMSuggestionRecord]
    cache_hits: int = 0
    cache_misses: int = 0


class LLMSuggestionsListResponse(StrictModel):
    plan_id: str
    suggestions: list[LLMSuggestionRecord]


class LLMSuggestionApplyRequest(StrictModel):
    expected_plan_hash: str


class LLMSuggestionRejectRequest(StrictModel):
    reason_code: str = "user_rejected"


class LLMSuggestionApplyResponse(StrictModel):
    plan_id: str
    plan_hash: str
    item: PlanItem
    affected_items: list[PlanItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    suggestion: LLMSuggestionRecord


class LLMSuggestionRejectResponse(StrictModel):
    plan_id: str
    suggestion: LLMSuggestionRecord


class RuleTestRequest(StrictModel):
    filename: str
    settings_override: dict[str, Any] = Field(default_factory=dict)


class RuleTestResponse(StrictModel):
    suggestion: RuleSuggestion
    validation_preview: list[ValidationIssue] = Field(default_factory=list)


class SettingsExportResponse(StrictModel):
    settings: dict[str, Any]
    exported_at: str
    app_version: str
    format_version: int = 1


class SettingsImportRequest(StrictModel):
    settings: dict[str, Any]
    dry_run: bool = True


class SettingsImportResponse(StrictModel):
    dry_run: bool
    applied: bool = False
    settings: dict[str, Any]
    changes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CorpusFixtureSummary(StrictModel):
    name: str
    total: int
    passed: int
    failed: int


class CorpusReportResponse(StrictModel):
    summary: dict[str, int]
    by_fixture: list[CorpusFixtureSummary]
    failures: list[str] = Field(default_factory=list)


class ExecuteRequest(StrictModel):
    root_path: str | None = None
    items: list[PlanItem] | None = None
    confirm: bool = False


class OperationRecord(StrictModel):
    run_id: str
    timestamp: str
    action: str
    source_path: str
    target_path: str
    status: str
    message: str = ""
    size: int = 0
    mtime: float = 0.0


class ExecutionItem(StrictModel):
    id: str
    run_id: str
    plan_item_id: str
    operation: Operation
    state: RunItemState
    source_path: str
    target_path: str
    temp_path: str = ""
    message: str = ""
    issue_code: str = ""
    snapshot: FileSnapshot | None = None
    created_at: str = ""
    updated_at: str = ""


class ExecutionRun(StrictModel):
    run_id: str
    plan_id: str = ""
    plan_hash: str = ""
    state: RunState
    summary: dict[str, int] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class ExecuteResponse(StrictModel):
    run_id: str
    operations: list[OperationRecord] = Field(default_factory=list)
    items: list[ExecutionItem] = Field(default_factory=list)
    summary: dict[str, int]
    state: RunState | None = None


class RunSummary(StrictModel):
    run_id: str
    timestamp: str = ""
    status: str = ""
    state: RunState | str = ""
    summary: dict[str, int]


class RollbackResult(StrictModel):
    run_id: str
    rollback_run_id: str
    state: RunState
    items: list[ExecutionItem] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class QuarantineManifest(StrictModel):
    run_id: str
    item_id: str
    original_abs_path: str
    original_rel_path: str
    quarantine_abs_path: str
    size: int
    created_ns: int
    modified_ns: int
    reason: str
    restore_status: Literal["available", "restored", "conflict", "missing"] = "available"
