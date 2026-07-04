from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .constants import AD_DOMAIN_PATTERNS, JUNK_EXTENSIONS, TEXT_JUNK_EXTENSIONS, VIDEO_EXTENSIONS
from .models import FileItem, PlanItem, PlanRequest, PlanResponse
from .paths import normalize_extension
from .scanner import file_id


@dataclass
class CodeInfo:
    code: str
    raw: str
    pattern: str
    confidence: float
    match_start: int
    match_end: int
    part_suffix: str = ""
    variant: str = ""
    removed_tokens: list[str] = field(default_factory=list)


CODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("fc2", re.compile(r"(?i)(?<![A-Z0-9])FC2[-_\s]?PPV[-_\s]?([0-9]{5,8})(?![0-9])")),
    ("numeric_underscore", re.compile(r"(?i)(?<![0-9])([0-9]{6})_([0-9]{2,4})(?![0-9])")),
    ("mixed_prefix", re.compile(r"(?i)(?<![A-Z0-9])([0-9]{2,4}[A-Z]{2,8})[-_\s]?([0-9]{1,5})(?![A-Z0-9])")),
    ("compact", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,8})([0-9]{3,5})(?![A-Z0-9])")),
    ("suffix_variant", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,12}[0-9]{0,4})[-_\s]?([0-9]{3,5})([A-Z])(?=$|[\s._-])")),
    ("standard", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,12}[0-9]{0,4})[-_\s]+([0-9]{1,8})(?![A-Z0-9])")),
]

AD_DOMAIN_REGEXES = [re.compile(pattern) for pattern in AD_DOMAIN_PATTERNS]
GENERIC_DOMAIN_RE = re.compile(r"(?i)(?:^|[\s@\[\]【】(_-])([a-z0-9-]+\.)+(com|net|org|tv|xyz|cc|me)(?:@)?")
BRACKET_AD_RE = re.compile(r"(?i)[\[【(（][^\]】)）]*(?:\.com|\.net|\.tv|\.xyz|\.cc|广告|最新地址|x18r|hhd800)[^\]】)）]*[\]】)）]")
PART_RE = re.compile(r"(?i)^(?:[\s._-]*(?:part|pt|cd|disc|disk)?[\s._-]*)([0-9]{1,2})(?=$|[\s._-])")
VARIANT_RE = re.compile(
    r"(?i)^(?:[\s._-]+)(C|UC|U|LEAK|UNCENSORED|UNCENSORED[-_\s]?LEAK|CH|SUB|SUBBED|4K|VR)(?=$|[\s._-])"
)


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def clean_prefix(prefix: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", prefix).upper()


def clean_number(number: str) -> str:
    return re.sub(r"[^0-9]", "", number)


def clean_id(prefix: str, number: str, *, keep_underscore: bool = False) -> str | None:
    p = clean_prefix(prefix)
    n = clean_number(number)
    if not p or not n:
        return None
    if p == "FC2PPV":
        return f"FC2PPV-{n}"
    if keep_underscore:
        return f"{p}_{n}"
    return f"{p}-{n}"


def removed_tokens_from_name(stem: str) -> list[str]:
    tokens: list[str] = []
    for regex in AD_DOMAIN_REGEXES:
        for match in regex.finditer(stem):
            tokens.append(match.group(0))
    for match in GENERIC_DOMAIN_RE.finditer(stem):
        tokens.append(match.group(0).strip(" @[]【】()_-"))
    for match in BRACKET_AD_RE.finditer(stem):
        tokens.append(match.group(0))
    return sorted(set(token for token in tokens if token))


def detection_text(stem: str) -> str:
    text = stem
    for regex in AD_DOMAIN_REGEXES:
        text = regex.sub(" ", text)
    text = GENERIC_DOMAIN_RE.sub(" ", text)
    text = BRACKET_AD_RE.sub(" ", text)
    return text


def parse_tail(text: str, match_end: int) -> tuple[str, str]:
    tail = text[match_end:].strip()
    part_suffix = ""
    variant = ""

    part_match = PART_RE.match(tail)
    if part_match:
        part_suffix = f"-{int(part_match.group(1))}"
        tail = tail[part_match.end() :].strip()

    variant_match = VARIANT_RE.match(tail)
    if variant_match:
        raw = variant_match.group(1)
        variant = "-" + re.sub(r"[\s_]+", "-", raw.upper())

    compact_variant = re.match(r"(?i)^([A-Z])(?=$|[\s._-])", tail)
    if not variant and compact_variant:
        variant = "-" + compact_variant.group(1).upper()

    return part_suffix, variant


def extract_media_code(name: str) -> CodeInfo | None:
    stem = Path(name).stem
    original_text = normalize_text(stem)
    text = detection_text(original_text)
    for pattern_name, pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if pattern_name == "fc2":
            code = f"FC2PPV-{match.group(1)}"
        elif pattern_name == "numeric_underscore":
            code = f"{match.group(1)}_{match.group(2)}"
        elif pattern_name == "suffix_variant":
            code = clean_id(match.group(1), match.group(2))
            if code is None:
                continue
        else:
            code = clean_id(match.group(1), match.group(2))
            if code is None:
                continue
        part_suffix, variant = parse_tail(text, match.end())
        if pattern_name == "suffix_variant":
            variant = "-" + match.group(3).upper()
        return CodeInfo(
            code=code,
            raw=match.group(0),
            pattern=pattern_name,
            confidence=0.92 if pattern_name != "numeric_underscore" else 0.78,
            match_start=match.start(),
            match_end=match.end(),
            part_suffix=part_suffix,
            variant=variant,
            removed_tokens=removed_tokens_from_name(stem),
        )
    return None


def is_junk_file(item: FileItem, custom_keywords: list[str], trash_zero_byte: bool) -> tuple[bool, str]:
    ext = normalize_extension(item.extension)
    lower_name = item.name.lower()
    if ext in JUNK_EXTENSIONS:
        return True, "download residue or shortcut"
    if trash_zero_byte and item.size == 0:
        return True, "empty file"
    if ext in TEXT_JUNK_EXTENSIONS:
        if any(regex.search(item.name) for regex in AD_DOMAIN_REGEXES):
            return True, "advertising text/html file"
        if any(keyword.lower() in lower_name for keyword in custom_keywords if keyword.strip()):
            return True, "custom junk keyword"
    return False, ""


def build_suggested_name(code_info: CodeInfo, extension: str) -> str:
    return f"{code_info.code}{code_info.part_suffix}{code_info.variant}{extension.lower()}"


def build_plan(request: PlanRequest) -> PlanResponse:
    root = Path(request.root_path).resolve(strict=False)
    items: list[PlanItem] = []

    for file_item in request.files:
        ext = normalize_extension(file_item.extension)
        source_path = Path(file_item.path)
        target_path = source_path
        suggested_name = file_item.name
        action = "keep"
        source = "rule"
        confidence = 1.0
        reason = "kept"
        warnings: list[str] = []
        media_code = ""
        part_suffix = ""
        variant = ""
        removed_tokens: list[str] = []
        checked = False

        junk, junk_reason = is_junk_file(
            file_item,
            request.rules.custom_junk_keywords,
            request.rules.trash_zero_byte,
        )
        if junk:
            action = "quarantine"
            confidence = 0.96
            reason = junk_reason
            checked = True
        elif ext in VIDEO_EXTENSIONS or file_item.kind == "media":
            code_info = extract_media_code(file_item.name)
            if code_info:
                suggested_name = build_suggested_name(code_info, ext)
                target_path = source_path.with_name(suggested_name)
                media_code = code_info.code
                part_suffix = code_info.part_suffix
                variant = code_info.variant
                removed_tokens = code_info.removed_tokens
                confidence = code_info.confidence
                if source_path.name == suggested_name:
                    action = "keep"
                    reason = "already clean"
                    checked = False
                else:
                    action = "rename"
                    reason = "keep detected media code"
                    checked = True
            else:
                action = "review"
                source = "rule"
                confidence = 0.0
                reason = "media code not detected"
                checked = False
                warnings.append("未识别番号")

        items.append(
            PlanItem(
                id=file_item.id or file_id(file_item.path),
                source_path=str(source_path),
                original_name=file_item.name,
                suggested_name=suggested_name,
                target_path=str(target_path),
                action=action,  # type: ignore[arg-type]
                source=source,  # type: ignore[arg-type]
                confidence=confidence,
                reason=reason,
                warnings=warnings,
                checked=checked,
                relative_path=file_item.relative_path,
                extension=ext,
                size=file_item.size,
                mtime=file_item.mtime,
                media_code=media_code,
                part_suffix=part_suffix,
                variant=variant,
                removed_tokens=removed_tokens,
            )
        )

    apply_cd_suffixes(items)
    validate_plan_items(root, items)
    summary = dict(Counter(item.action for item in items))
    return PlanResponse(root_path=str(root), items=items, summary=summary)


def apply_cd_suffixes(items: list[PlanItem]) -> None:
    grouped: dict[tuple[str, str], list[PlanItem]] = defaultdict(list)
    for item in items:
        if item.action != "rename":
            continue
        target = Path(item.target_path)
        grouped[(str(target.parent).lower(), target.name.lower())].append(item)

    for group_items in grouped.values():
        if len(group_items) <= 1:
            continue
        ordered = sorted(group_items, key=lambda item: item.original_name.lower())
        for index, item in enumerate(ordered, start=1):
            old_target = Path(item.target_path)
            base = old_target.stem
            item.suggested_name = f"{base}-CD{index:02d}{old_target.suffix.lower()}"
            item.target_path = str(old_target.with_name(item.suggested_name))
            item.warnings.append("同目录同名冲突，已追加 CD 编号")


def validate_plan_items(root: Path, items: list[PlanItem]) -> None:
    target_counts = Counter(
        str(Path(item.target_path).resolve(strict=False)).lower()
        for item in items
        if item.action in {"rename", "quarantine"} and item.checked
    )
    for item in items:
        if item.action == "rename":
            validate_rename_item(root, item, target_counts)


def validate_rename_item(root: Path, item: PlanItem, target_counts: Counter[str]) -> None:
    from .validator import validate_target_name

    target = Path(item.target_path).resolve(strict=False)
    source = Path(item.source_path).resolve(strict=False)
    problems = validate_target_name(item.suggested_name, item.extension)
    item.warnings.extend(problems)

    try:
        target.relative_to(root)
        source.relative_to(root)
    except ValueError:
        item.warnings.append("路径越界")

    target_key = str(target).lower()
    source_key = str(source).lower()
    if target_counts[target_key] > 1:
        item.warnings.append("目标文件名重复")
    if target.exists() and target_key != source_key:
        item.warnings.append("目标文件已存在")
    if target_key == source_key and str(target) != str(source):
        item.warnings.append("仅大小写变化，将使用临时文件名过渡")
    if len(str(target)) > 240:
        item.warnings.append("目标路径过长")

    blocking = {"路径越界", "目标文件名重复", "目标文件已存在", "目标路径过长"}
    if any(warning in blocking for warning in item.warnings):
        item.checked = False
