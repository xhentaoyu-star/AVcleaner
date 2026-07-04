from __future__ import annotations

import hashlib
import re

from .paths import normalize_extension

SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
NFO_EXTENSIONS = {".nfo"}
SIDECAR_TYPE_BY_EXTENSION = {
    **{ext: "subtitle" for ext in SUBTITLE_EXTENSIONS},
    **{ext: "image" for ext in IMAGE_EXTENSIONS},
    **{ext: "nfo" for ext in NFO_EXTENSIONS},
}

LANGUAGE_SUFFIX_RE = re.compile(
    r"(?i)\.("
    r"zh|chs|cht|cn|en|ja|jp|ko|"
    r"zh[-_](?:cn|tw|hans|hant)"
    r")$"
)


def classify_sidecar_type(extension: str) -> str | None:
    return SIDECAR_TYPE_BY_EXTENSION.get(normalize_extension(extension))


def split_subtitle_language_suffix(stem: str, extension: str) -> tuple[str, str]:
    if normalize_extension(extension) not in SUBTITLE_EXTENSIONS:
        return stem, ""
    match = LANGUAGE_SUFFIX_RE.search(stem)
    if not match:
        return stem, ""
    return stem[: match.start()], match.group(1)


def group_id_for_media_code(media_code: str | None) -> str:
    if not media_code:
        return ""
    digest = hashlib.sha1(media_code.upper().encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"media_{digest}"
