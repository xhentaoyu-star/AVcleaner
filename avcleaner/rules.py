from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .constants import (
    ADVERTISING_DIRECTORY_NAMES,
    AD_DOMAIN_PATTERNS,
    JUNK_EXTENSIONS,
    LARGE_TEMP_JUNK_EXTENSIONS,
    LARGE_TEMP_JUNK_REVIEW_BYTES,
    OBVIOUS_ADVERTISING_FILENAME_TOKENS,
    RULE_TRACE_IDS,
    SIDECAR_EXTENSIONS,
    TEXT_JUNK_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from .models import FileItem, PlanItem, PlanRequest, PlanResponse, RuleConfig, RuleSuggestion, RuleTraceStep
from .paths import normalize_extension
from .scanner import file_id
from .sidecars import classify_sidecar_type, split_subtitle_language_suffix


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


@dataclass(frozen=True)
class CodeCandidate:
    code: str
    raw: str
    pattern: str
    confidence: float
    match_start: int
    match_end: int
    part_suffix: str = ""
    variant: str = ""


VALID_RULE_IDS = set(RULE_TRACE_IDS)

CODE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("fc2", re.compile(r"(?i)(?<![A-Z0-9])FC2[-_\s]?PPV[-_\s]?([0-9]{5,8})(?![0-9])")),
    ("numeric_underscore", re.compile(r"(?i)(?<![0-9])([0-9]{6})[_\s]+([0-9]{2,4})(?![0-9])")),
    ("mixed_prefix", re.compile(r"(?i)(?<![A-Z0-9])([0-9]{2,4}[A-Z]{2,8})[-_\s]?([0-9]{1,5})(?![A-Z0-9])")),
    ("suffix_variant", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,12}[0-9]{0,4})[-_\s]?([0-9]{3,5})([A-Z])(?=$|[\s._-])")),
    ("standard", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,12}[0-9]{0,4})[-_\s]+([0-9]{1,8})(?![A-Z0-9])")),
    ("compact", re.compile(r"(?i)(?<![A-Z0-9])([A-Z]{2,8})([0-9]{3,5})(?![A-Z0-9])")),
]

AD_DOMAIN_REGEXES = [re.compile(pattern) for pattern in AD_DOMAIN_PATTERNS]
GENERIC_DOMAIN_RE = re.compile(r"(?i)(?:^|[\s@\[\](_-])((?:[a-z0-9-]+\.)+(?:com|net|org|tv|xyz|cc|me))(?:@)?")
BRACKET_SEGMENT_RE = re.compile(r"[\[({<]([^\])}>]{1,80})[\])}>]")
PART_RE = re.compile(r"(?i)^(?:[\s._-]*(?:part|pt|cd|disc|disk)?[\s._-]*)([0-9]{1,2})(?=$|[\s._-])")
VARIANT_RE = re.compile(r"(?i)^(?:[\s._-]+)?(UC|U|C|LEAK|UNCENSORED(?:[-_\s]?LEAK)?|CH|SUB|SUBBED|VR)(?=$|[\s._-])")
DATE_TOKEN_RE = re.compile(r"(?<![0-9])20[0-9]{2}[-_.][0-9]{2}[-_.][0-9]{2}(?![0-9])")
NOISE_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Z0-9])(?:1080P|720P|2160P|4K|H264|H265|X264|X265|HEVC|AV1|10BIT|8BIT|AAC|FLAC|WEB[-_\s]?DL|BLURAY)(?![A-Z0-9])"
)
WINDOWS_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SEPARATOR_RE = re.compile(r"[\s._-]+")
NOISE_PREFIXES = {"AAC", "FLAC", "HEVC", "WEB", "BLURAY", "H264", "H265", "X264", "X265", "AV1", "BIT"}
BRACKET_AD_MARKERS = ("com", "net", "org", "tv", "xyz", "cc", "hhd800", "x18r", "promo", "ad", "release")
MAX_RULE_TEST_FILENAME_LENGTH = 255
MAX_REMOVED_TOKENS_PER_STEP = 20
MAX_WARNINGS_PER_TRACE_STEP = 20
MAX_SUGGESTION_WARNINGS = 20
MAX_TRACE_STEPS = 12


def _bounded(values: list[str] | None, limit: int) -> tuple[list[str], bool]:
    raw = list(values or [])
    if len(raw) <= limit:
        return raw, False
    return raw[:limit], True


def _step(
    rule_id: str,
    before: str,
    after: str,
    *,
    removed_tokens: list[str] | None = None,
    preserved_tokens: list[str] | None = None,
    confidence_delta: float | None = None,
    warnings: list[str] | None = None,
) -> RuleTraceStep:
    removed, removed_truncated = _bounded(removed_tokens, MAX_REMOVED_TOKENS_PER_STEP)
    preserved, preserved_truncated = _bounded(preserved_tokens, MAX_REMOVED_TOKENS_PER_STEP)
    bounded_warnings, warnings_truncated = _bounded(warnings, MAX_WARNINGS_PER_TRACE_STEP)
    if (removed_truncated or preserved_truncated or warnings_truncated) and "trace_truncated" not in bounded_warnings:
        bounded_warnings.append("trace_truncated")
    return RuleTraceStep(
        rule_id=rule_id,
        before=before,
        after=after,
        removed_tokens=removed,
        preserved_tokens=preserved,
        confidence_delta=confidence_delta,
        warnings=bounded_warnings,
    )


def _bounded_suggestion_warnings(warnings: list[str]) -> list[str]:
    bounded, truncated = _bounded(warnings, MAX_SUGGESTION_WARNINGS)
    if truncated and "trace_truncated" not in bounded:
        bounded.append("trace_truncated")
    return bounded


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
    if p in NOISE_PREFIXES:
        return None
    if p == "FC2PPV":
        return f"FC2-PPV-{n}"
    if keep_underscore:
        return f"{p}_{n}"
    return f"{p}-{n}"


def _collapse_separators(value: str) -> str:
    return SEPARATOR_RE.sub(" ", value).strip(" ._-")


def _replace_with_space(text: str, matches: list[re.Match[str]]) -> str:
    if not matches:
        return text
    result = text
    for match in sorted(matches, key=lambda item: item.start(), reverse=True):
        result = result[: match.start()] + " " + result[match.end() :]
    return _collapse_separators(result)


def _custom_domain_regexes(domains: list[str]) -> list[re.Pattern[str]]:
    return [
        re.compile(r"(?i)(?:^|[\s@\[\](_-])(" + re.escape(domain) + r")(?:@)?")
        for domain in domains
        if domain.strip()
    ]


def remove_ad_domains(stem: str, extra_domains: list[str] | None = None) -> tuple[str, list[str]]:
    text = stem
    removed: list[str] = []
    changed = False
    for regex in [*AD_DOMAIN_REGEXES, *_custom_domain_regexes(extra_domains or [])]:
        for match in regex.finditer(text):
            token = (match.group(1) if match.lastindex else match.group(0)).strip(" @[]()_-")
            if token:
                removed.append(token)
                changed = True
        text = regex.sub(" ", text)
    for match in GENERIC_DOMAIN_RE.finditer(text):
        token = match.group(1) if match.lastindex else match.group(0)
        token = token.strip(" @[]()_-")
        if token:
            removed.append(token)
            changed = True
    text = GENERIC_DOMAIN_RE.sub(" ", text)
    if not changed:
        return stem, []
    return _collapse_separators(text), sorted(set(removed))


def remove_bracket_ads(stem: str) -> tuple[str, list[str]]:
    matches = []
    removed = []
    for match in BRACKET_SEGMENT_RE.finditer(stem):
        body = match.group(1).lower()
        if any(marker in body for marker in BRACKET_AD_MARKERS):
            matches.append(match)
            removed.append(match.group(0))
    return _replace_with_space(stem, matches), removed


def remove_noise_tokens(stem: str, extra_tokens: list[str] | None = None) -> tuple[str, list[str]]:
    matches = list(NOISE_TOKEN_RE.finditer(stem)) + list(DATE_TOKEN_RE.finditer(stem))
    for token in extra_tokens or []:
        if token.strip():
            pattern = re.compile(r"(?i)(?<![A-Z0-9])" + re.escape(token.strip()) + r"(?![A-Z0-9])")
            matches.extend(pattern.finditer(stem))
    removed = []
    for match in matches:
        token = match.group(0)
        if re.fullmatch(r"(?i)WEB[-_\s]?DL", token):
            token = "WEB-DL"
        removed.append(token)
    return _replace_with_space(stem, matches), sorted(set(removed))


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

    compact_variant = re.match(r"(?i)^[\s._-]*([A-Z])(?=$|[\s._-])", tail)
    if not variant and compact_variant:
        variant = "-" + compact_variant.group(1).upper()

    return part_suffix, variant


def _candidate_from_match(pattern_name: str, match: re.Match[str], text: str) -> CodeCandidate | None:
    if pattern_name == "fc2":
        code = f"FC2-PPV-{match.group(1)}"
        confidence = 0.95
    elif pattern_name == "numeric_underscore":
        code = f"{match.group(1)}_{match.group(2)}"
        confidence = 0.78
    elif pattern_name == "suffix_variant":
        code = clean_id(match.group(1), match.group(2))
        confidence = 0.9
    else:
        if pattern_name == "standard" and match.group(1)[-1:].isdigit() and len(clean_number(match.group(2))) <= 2:
            return None
        code = clean_id(match.group(1), match.group(2))
        confidence = 0.92 if pattern_name != "compact" else 0.86
    if code is None:
        return None
    part_suffix, variant = parse_tail(text, match.end())
    if pattern_name == "suffix_variant":
        variant = "-" + match.group(3).upper()
    return CodeCandidate(
        code=code,
        raw=match.group(0),
        pattern=pattern_name,
        confidence=confidence,
        match_start=match.start(),
        match_end=match.end(),
        part_suffix=part_suffix,
        variant=variant,
    )


def detect_code_candidates(stem: str) -> list[CodeCandidate]:
    candidates: list[CodeCandidate] = []
    for pattern_name, pattern in CODE_PATTERNS:
        for match in pattern.finditer(stem):
            candidate = _candidate_from_match(pattern_name, match, stem)
            if candidate:
                candidates.append(candidate)
    accepted: list[CodeCandidate] = []
    seen_codes: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (-item.confidence, item.match_start)):
        overlaps = any(candidate.match_start < other.match_end and candidate.match_end > other.match_start for other in accepted)
        if overlaps or candidate.code in seen_codes:
            continue
        accepted.append(candidate)
        seen_codes.add(candidate.code)
    return sorted(accepted, key=lambda item: item.match_start)


def _safe_windows_name(name: str) -> tuple[str, list[str]]:
    cleaned = WINDOWS_UNSAFE_RE.sub("_", name).rstrip(" .")
    warnings = []
    if cleaned != name:
        warnings.append("windows_name_cleaned")
    return cleaned or name, warnings


def _extension_for(filename: str) -> str:
    return Path(filename).suffix


def _stem_for(filename: str, extension: str) -> str:
    return filename[: -len(extension)] if extension else filename


def _rule_enabled(settings: RuleConfig, rule_id: str) -> bool:
    return settings.enabled_rules.get(rule_id, True)


def _is_segment_suffix(value: str) -> bool:
    return bool(re.fullmatch(r"-[A-Z]", value or ""))


def _render_template(
    settings: RuleConfig,
    *,
    code: str,
    part: str,
    variant: str,
    language: str,
    ext: str,
) -> str:
    return settings.output_template.format(code=code, part=part, variant=variant, language=language, ext=ext)


def suggest_name_with_trace(filename: str, settings: RuleConfig | None = None) -> RuleSuggestion:
    settings = settings or RuleConfig()
    original_name = filename
    extension = _extension_for(filename)
    preserved_extension = extension.lower()
    stem = _stem_for(filename, extension)
    sidecar_type = classify_sidecar_type(preserved_extension)
    language_suffix = ""
    trace: list[RuleTraceStep] = []
    warnings: list[str] = []

    current = normalize_text(stem) if _rule_enabled(settings, "unicode_normalize") else stem
    if current != stem:
        trace.append(_step("unicode_normalize", stem, current))

    trimmed = current.strip(" ._-") if _rule_enabled(settings, "trim_spaces") else current
    if trimmed != current:
        trace.append(_step("trim_spaces", current, trimmed, removed_tokens=[current[: len(current) - len(current.lstrip(" ._-"))].strip()]))
    current = trimmed
    minimal_no_code_stem = current

    language_base, detected_language = split_subtitle_language_suffix(current, preserved_extension)
    if detected_language:
        language_suffix = detected_language
        if _rule_enabled(settings, "detect_sidecar_language"):
            trace.append(_step("detect_sidecar_language", current, language_base, preserved_tokens=[language_suffix]))
        current = language_base

    after_ad, removed_domains = remove_ad_domains(current, settings.remove_ad_domains) if _rule_enabled(settings, "remove_ad_domain") else (current, [])
    if after_ad != current:
        trace.append(_step("remove_ad_domain", current, after_ad, removed_tokens=removed_domains))
    current = after_ad

    if settings.remove_bracket_ads and _rule_enabled(settings, "remove_bracket_ad"):
        after_brackets, removed_brackets = remove_bracket_ads(current)
        if after_brackets != current:
            trace.append(_step("remove_bracket_ad", current, after_brackets, removed_tokens=removed_brackets))
        current = after_brackets

    noise_tokens = [*settings.remove_noise_tokens, *settings.custom_remove_tokens]
    after_noise, removed_noise = remove_noise_tokens(current, noise_tokens) if _rule_enabled(settings, "remove_noise_token") else (current, [])
    if after_noise != current:
        trace.append(_step("remove_noise_token", current, after_noise, removed_tokens=removed_noise))
    current = after_noise

    candidates = detect_code_candidates(current)
    if not candidates:
        warnings.append("media_code_not_detected")
        rendered = f"{minimal_no_code_stem}{extension}"
        suggested_name, safe_warnings = _safe_windows_name(rendered)
        warnings.extend(safe_warnings)
        warnings = _bounded_suggestion_warnings(warnings)
        if not trace:
            trace.append(_step("detect_media_code", original_name, original_name, warnings=warnings))
        if suggested_name != rendered:
            trace.append(_step("windows_safe_name", rendered, suggested_name, warnings=safe_warnings))
        trace.append(_step("render_template", original_name, suggested_name, warnings=warnings))
        return RuleSuggestion(
            original_name=original_name,
            suggested_name=suggested_name,
            media_code=None,
            language_suffix=language_suffix,
            sidecar_type=sidecar_type if sidecar_type in {"subtitle", "image", "nfo"} else None,
            confidence=0.0,
            trace=trace,
            warnings=warnings,
            requires_review=True,
        )

    candidates = sorted(candidates, key=lambda item: (-item.confidence, item.match_start))
    chosen = candidates[0]
    render_code = chosen.raw if settings.media_code_style == "preserve_existing" else chosen.code
    if settings.normalize_case:
        render_code = render_code.upper()
    if len(candidates) > 1:
        warnings.append("multiple_media_code_candidates")
    trace.append(
        _step(
            "detect_media_code",
            current,
            chosen.raw,
            preserved_tokens=[chosen.raw],
            confidence_delta=chosen.confidence,
            warnings=warnings,
        )
    )
    if chosen.raw != render_code and _rule_enabled(settings, "normalize_media_code"):
        trace.append(_step("normalize_media_code", chosen.raw, render_code, preserved_tokens=[render_code]))
    part_suffix = chosen.part_suffix if settings.preserve_part_suffix and settings.keep_part_suffix else ""
    segment_suffix = chosen.variant if _is_segment_suffix(chosen.variant) and settings.preserve_part_suffix and settings.keep_part_suffix else ""
    variant = "" if segment_suffix else (chosen.variant if settings.preserve_variant else "")
    if part_suffix and _rule_enabled(settings, "detect_part_suffix"):
        trace.append(_step("detect_part_suffix", current[chosen.match_end :].strip(), part_suffix, preserved_tokens=[part_suffix]))
    if segment_suffix and _rule_enabled(settings, "detect_segment_suffix"):
        trace.append(_step("detect_segment_suffix", current[chosen.match_end :].strip(), segment_suffix, preserved_tokens=[segment_suffix]))
    if segment_suffix and _rule_enabled(settings, "preserve_segment_suffix"):
        trace.append(_step("preserve_segment_suffix", render_code, f"{render_code}{segment_suffix}", preserved_tokens=[segment_suffix]))
    if variant and _rule_enabled(settings, "detect_variant"):
        trace.append(_step("detect_variant", current[chosen.match_end :].strip(), variant, preserved_tokens=[variant]))
    language_part = f".{language_suffix}" if language_suffix else ""
    if language_suffix and settings.preserve_sidecar_language and _rule_enabled(settings, "preserve_sidecar_language"):
        before_language = f"{render_code}{part_suffix}{segment_suffix}{variant}"
        trace.append(
            _step(
                "preserve_sidecar_language",
                before_language,
                f"{before_language}{language_part}",
                preserved_tokens=[language_suffix],
            )
        )
    ext_part = preserved_extension if settings.preserve_extension else ""
    if ext_part and _rule_enabled(settings, "preserve_extension"):
        trace.append(_step("preserve_extension", original_name, preserved_extension, preserved_tokens=[preserved_extension]))

    rendered = _render_template(settings, code=render_code, part=part_suffix, variant=f"{segment_suffix}{variant}", language=language_part, ext=ext_part)
    safe_name, safe_warnings = _safe_windows_name(rendered)
    warnings.extend(safe_warnings)
    warnings = _bounded_suggestion_warnings(warnings)
    if safe_name != rendered:
        trace.append(_step("windows_safe_name", rendered, safe_name, warnings=safe_warnings))
    suggested_name = safe_name
    trace.append(
        _step(
            "render_template",
            original_name,
            suggested_name,
            preserved_tokens=[render_code, part_suffix, segment_suffix, variant, language_part, ext_part],
            warnings=warnings,
        )
    )

    requires_review = bool(warnings) or chosen.confidence < settings.review_threshold
    return RuleSuggestion(
        original_name=original_name,
        suggested_name=suggested_name,
        media_code=render_code,
        part_suffix=part_suffix,
        variant=f"{segment_suffix}{variant}",
        language_suffix=language_suffix,
        sidecar_type=sidecar_type if sidecar_type in {"subtitle", "image", "nfo"} else None,
        confidence=chosen.confidence,
        trace=trace,
        warnings=warnings,
        requires_review=requires_review,
    )


def removed_tokens_from_name(stem: str) -> list[str]:
    after_domains, domains = remove_ad_domains(stem)
    _after_brackets, brackets = remove_bracket_ads(after_domains)
    return sorted(set(domains + brackets))


def detection_text(stem: str) -> str:
    text, _domains = remove_ad_domains(normalize_text(stem))
    text, _brackets = remove_bracket_ads(text)
    text, _noise = remove_noise_tokens(text)
    return text


def extract_media_code(name: str) -> CodeInfo | None:
    suggestion = suggest_name_with_trace(name)
    if suggestion.media_code is None:
        return None
    return CodeInfo(
        code=suggestion.media_code,
        raw=suggestion.media_code,
        pattern="rule_trace",
        confidence=suggestion.confidence,
        match_start=0,
        match_end=len(suggestion.media_code),
        part_suffix=suggestion.part_suffix,
        variant=suggestion.variant,
        removed_tokens=[
            token
            for step in suggestion.trace
            for token in step.removed_tokens
        ],
    )


def is_junk_file(item: FileItem, custom_keywords: list[str], trash_zero_byte: bool) -> tuple[bool, str]:
    ext = normalize_extension(item.extension)
    lower_name = item.name.lower()
    compact_name = re.sub(r"\s+", "", normalize_text(item.name)).casefold()
    parent_names = {
        normalize_text(part).strip().casefold()
        for part in Path(item.path).parent.parts
    }
    if parent_names & {name.casefold() for name in ADVERTISING_DIRECTORY_NAMES}:
        return True, "advertising_directory"
    if any(token in compact_name for token in OBVIOUS_ADVERTISING_FILENAME_TOKENS):
        return True, "obvious_advertising_filename"
    if ext in SIDECAR_EXTENSIONS:
        if any(keyword.lower() in lower_name for keyword in custom_keywords if keyword.strip()):
            return True, "custom_junk_keyword"
        return False, ""
    if ext in JUNK_EXTENSIONS:
        return True, "download_residue_or_shortcut"
    if trash_zero_byte and item.size == 0:
        return True, "empty_file"
    if ext in TEXT_JUNK_EXTENSIONS:
        if any(regex.search(item.name) for regex in AD_DOMAIN_REGEXES):
            return True, "advertising_text_or_html_file"
        if any(keyword.lower() in lower_name for keyword in custom_keywords if keyword.strip()):
            return True, "custom_junk_keyword"
    return False, ""


def large_temp_junk_requires_review(item: FileItem) -> bool:
    return normalize_extension(item.extension) in LARGE_TEMP_JUNK_EXTENSIONS and item.size >= LARGE_TEMP_JUNK_REVIEW_BYTES


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
        requires_review = False
        media_code = ""
        part_suffix = ""
        variant = ""
        removed_tokens: list[str] = []
        checked = False
        trace: list[RuleTraceStep] = []

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
            if large_temp_junk_requires_review(file_item):
                checked = False
                requires_review = True
                warnings.append("large_temp_file_requires_manual_selection")
        elif ext in VIDEO_EXTENSIONS or file_item.kind == "media":
            suggestion = suggest_name_with_trace(file_item.name, request.rules)
            trace = suggestion.trace
            warnings = suggestion.warnings
            if suggestion.media_code:
                suggested_name = suggestion.suggested_name
                target_path = source_path.with_name(suggested_name)
                media_code = suggestion.media_code
                part_suffix = suggestion.part_suffix
                variant = suggestion.variant
                removed_tokens = [token for step in trace for token in step.removed_tokens]
                confidence = suggestion.confidence
                if source_path.name == suggested_name:
                    action = "keep"
                    reason = "already_clean"
                    checked = False
                else:
                    action = "rename"
                    reason = "detected_media_code"
                    checked = True
            else:
                action = "review"
                source = "rule"
                confidence = suggestion.confidence
                reason = "media_code_not_detected"
                checked = False

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
                selected_default=checked,
                requires_review=requires_review,
                relative_path=file_item.relative_path,
                extension=ext,
                size=file_item.size,
                mtime=file_item.mtime,
                media_code=media_code,
                part_suffix=part_suffix,
                variant=variant,
                removed_tokens=removed_tokens,
                trace=trace,
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
            item.target_name = item.suggested_name
            item.target_path = str(old_target.with_name(item.suggested_name))
            item.warnings.append("duplicate_target_cd_suffix")


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
        item.warnings.append("path_escape")

    target_key = str(target).lower()
    source_key = str(source).lower()
    if target_counts[target_key] > 1:
        item.warnings.append("duplicate_target")
    if target.exists() and target_key != source_key:
        item.warnings.append("target_exists")
    if target_key == source_key and str(target) != str(source):
        item.warnings.append("case_only_rename")
    if len(str(target)) > 240:
        item.warnings.append("path_near_limit")

    blocking = {"path_escape", "duplicate_target", "target_exists"}
    if any(warning in blocking for warning in item.warnings):
        item.checked = False
