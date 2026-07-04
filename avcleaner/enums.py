from __future__ import annotations

from enum import StrEnum


class Operation(StrEnum):
    KEEP = "keep"
    RENAME = "rename"
    REVIEW = "review"
    QUARANTINE = "quarantine"
    SKIP = "skip"


class SuggestionSource(StrEnum):
    RULE = "rule"
    LLM = "llm"
    MANUAL = "manual"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class IssueCode(StrEnum):
    TARGET_EXISTS = "target_exists"
    TARGET_EXISTS_CASE_INSENSITIVE = "target_exists_case_insensitive"
    DUPLICATE_TARGET = "duplicate_target"
    DUPLICATE_TARGET_CASE_INSENSITIVE = "duplicate_target_case_insensitive"
    PATH_ESCAPE = "path_escape"
    EXTENSION_CHANGED = "extension_changed"
    EMPTY_NAME = "empty_name"
    INVALID_CHARACTER = "invalid_character"
    CONTROL_CHARACTER = "control_character"
    TRAILING_DOT_OR_SPACE = "trailing_dot_or_space"
    RESERVED_NAME = "reserved_name"
    RESERVED_NAME_WITH_EXTENSION = "reserved_name_with_extension"
    ALTERNATE_DATA_STREAM = "alternate_data_stream"
    SOURCE_MISSING = "source_missing"
    SOURCE_CHANGED = "source_changed"
    PATH_TOO_LONG = "path_too_long"
    PATH_NEAR_LIMIT = "path_near_limit"
    CASE_ONLY_RENAME = "case_only_rename"
    TARGET_SAME_AS_SOURCE = "target_same_as_source"
    RESTORE_TARGET_EXISTS = "restore_target_exists"
    UNKNOWN_SELECTED_ITEM_IDS = "unknown_selected_item_ids"
    UNKNOWN_PLAN_ITEM = "unknown_plan_item"
    BLOCKING_ITEM_SELECTED = "blocking_item_selected"
    INVALID_TARGET_NAME = "invalid_target_name"
    PATH_SEPARATOR_IN_TARGET = "path_separator_in_target"
    NO_SELECTED_ITEMS = "no_selected_items"
    API_TOKEN_MISSING = "api_token_missing"
    API_TOKEN_INVALID = "api_token_invalid"
    PLAN_HASH_MISMATCH = "plan_hash_mismatch"
    LEGACY_EXECUTE_DISABLED = "legacy_execute_disabled"
    REQUEST_EXTRA_FIELDS = "request_extra_fields"
    LLM_AUTH_FAILED = "llm_auth_failed"
    LLM_REQUEST_FAILED = "llm_request_failed"
    LLM_SCHEMA_INVALID = "llm_schema_invalid"
    LLM_NOT_CONFIGURED = "llm_not_configured"
    LLM_PROVIDER_ERROR = "llm_provider_error"
    LLM_TIMEOUT = "llm_timeout"
    LLM_INVALID_JSON = "llm_invalid_json"
    LLM_SUGGESTION_INVALID = "llm_suggestion_invalid"
    LLM_PAYLOAD_PRIVACY_VIOLATION = "llm_payload_privacy_violation"
    LLM_CACHE_ERROR = "llm_cache_error"
    LEGACY_LLM_SUGGEST_DISABLED = "legacy_llm_suggest_disabled"
    SUGGESTION_NOT_FOUND = "suggestion_not_found"
    SUGGESTION_PLAN_MISMATCH = "suggestion_plan_mismatch"
    SUGGESTION_STALE = "suggestion_stale"
    SUGGESTION_VALIDATION_FAILED = "suggestion_validation_failed"
    BLOCKING_SUGGESTION = "blocking_suggestion"
    MANUAL_EDIT_CONFLICT = "manual_edit_conflict"


class PlanState(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    STALE = "stale"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class RunState(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLBACK_RUNNING = "rollback_running"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_PARTIAL = "rollback_partial"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    ABANDONED = "abandoned"


class RunItemState(StrEnum):
    PENDING = "pending"
    SKIPPED = "skipped"
    RENAMED = "renamed"
    QUARANTINED = "quarantined"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"
