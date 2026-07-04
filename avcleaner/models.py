from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .constants import SIDECAR_EXTENSIONS, VIDEO_EXTENSIONS


Action = Literal["keep", "rename", "review", "quarantine"]
SuggestionSource = Literal["rule", "llm", "manual"]


class RuleConfig(BaseModel):
    remove_bracket_ads: bool = True
    normalize_case: bool = True
    keep_part_suffix: bool = True
    trash_zero_byte: bool = True
    custom_remove_tokens: list[str] = Field(default_factory=list)
    custom_junk_keywords: list[str] = Field(default_factory=list)


class LLMSettings(BaseModel):
    provider: Literal["disabled", "openai_compatible", "ollama"] = "disabled"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.0
    max_batch_size: int = 20
    max_concurrency: int = 2
    send_full_path: bool = False


class AppSettings(BaseModel):
    video_extensions: list[str] = Field(default_factory=lambda: sorted(VIDEO_EXTENSIONS))
    sidecar_extensions: list[str] = Field(default_factory=lambda: sorted(SIDECAR_EXTENSIONS))
    exclude_dirs: list[str] = Field(default_factory=list)
    rules: RuleConfig = Field(default_factory=RuleConfig)
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


class ScanRequest(BaseModel):
    root_path: str
    recursive: bool = True
    include_hidden: bool = False
    extensions: list[str] | None = None
    exclude_dirs: list[str] | None = None


class FileItem(BaseModel):
    id: str
    path: str
    relative_path: str
    name: str
    stem: str
    extension: str
    size: int
    mtime: float
    kind: Literal["media", "sidecar", "junk", "other"]
    is_hidden: bool = False


class ScanResponse(BaseModel):
    root_path: str
    files: list[FileItem]
    total_files: int
    skipped_dirs: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    root_path: str
    files: list[FileItem]
    rules: RuleConfig = Field(default_factory=RuleConfig)
    use_llm: bool = False


class PlanItem(BaseModel):
    id: str
    source_path: str
    original_name: str
    suggested_name: str
    target_path: str
    action: Action
    source: SuggestionSource
    confidence: float = 0.0
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    checked: bool = True
    relative_path: str = ""
    extension: str = ""
    size: int = 0
    mtime: float = 0.0
    media_code: str = ""
    part_suffix: str = ""
    variant: str = ""
    removed_tokens: list[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    root_path: str
    items: list[PlanItem]
    summary: dict[str, int]


class LLMSuggestion(BaseModel):
    item_id: str
    suggested_name: str
    media_code: str = ""
    part_suffix: str = ""
    variant: str = ""
    removed_tokens: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)


class LLMBatchResponse(BaseModel):
    suggestions: list[LLMSuggestion]


class LLMSuggestItem(BaseModel):
    id: str
    name: str
    extension: str
    adjacent_names: list[str] = Field(default_factory=list)
    path: str | None = None


class LLMSuggestRequest(BaseModel):
    items: list[LLMSuggestItem]
    settings: LLMSettings | None = None


class ExecuteRequest(BaseModel):
    root_path: str
    items: list[PlanItem]
    confirm: bool = False


class OperationRecord(BaseModel):
    run_id: str
    timestamp: str
    action: str
    source_path: str
    target_path: str
    status: str
    message: str = ""
    size: int = 0
    mtime: float = 0.0


class ExecuteResponse(BaseModel):
    run_id: str
    operations: list[OperationRecord]
    summary: dict[str, int]


class RunSummary(BaseModel):
    run_id: str
    timestamp: str
    status: str
    summary: dict[str, int]

