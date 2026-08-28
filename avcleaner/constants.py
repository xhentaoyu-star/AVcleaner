from __future__ import annotations

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts"}
SIDECAR_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".nfo", ".jpg", ".jpeg", ".png", ".webp"}
JUNK_EXTENSIONS = {".url", ".torrent", ".parts", ".qkdownloading", ".xltd", ".aria2"}
TEXT_JUNK_EXTENSIONS = {".txt", ".html", ".htm", ".mht"}
OBVIOUS_ADVERTISING_FILENAME_TOKENS = {
    "18+游戏大全",
    "18+遊戲大全",
    "聚合全网h直播",
    "聚合全網h直播",
    "最新地址",
    "最新导航地址",
    "最新導航地址",
    "新片合集发布",
    "新片合集發佈",
    "更多精彩点击这里访问",
    "更多精彩點擊這裡訪問",
    "防屏蔽二维码",
    "防屏蔽二維碼",
    "论坛地址宣传图",
    "論壇地址宣傳圖",
}
ADVERTISING_DIRECTORY_NAMES = {"宣传文件", "宣傳文件"}
LARGE_TEMP_JUNK_EXTENSIONS = {".parts", ".qkdownloading", ".xltd", ".aria2"}
LARGE_TEMP_JUNK_REVIEW_BYTES = 1024 * 1024 * 1024

RULE_TRACE_IDS = {
    "unicode_normalize",
    "trim_spaces",
    "remove_ad_domain",
    "remove_bracket_ad",
    "remove_noise_token",
    "detect_media_code",
    "normalize_media_code",
    "detect_part_suffix",
    "detect_segment_suffix",
    "preserve_segment_suffix",
    "detect_variant",
    "detect_sidecar_language",
    "preserve_sidecar_language",
    "preserve_extension",
    "render_template",
    "manual_edit",
    "llm_accept",
    "windows_safe_name",
}

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".codegraph",
    ".codex",
    ".agents",
    ".tools",
    ".venv",
    "__pycache__",
    "node_modules",
    "OpenAver",
    "prowlarr",
    "quarantine",
    "_media_cleanup",
    "AVcleaner",
}

AD_DOMAIN_PATTERNS = [
    r"(?i)hhd800\.com",
    r"(?i)489155\.com",
    r"(?i)226655\.xyz",
    r"(?i)x18r\.tv",
    r"(?i)nyap2p\.com",
    r"(?i)996gg\.cc",
    r"(?i)thzsub\.com",
    r"(?i)javday\.tv",
    r"(?i)7mmtv\.",
    r"(?i)18\+.*996gg\.cc",
]

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
