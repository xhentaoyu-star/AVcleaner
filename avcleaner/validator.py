from __future__ import annotations

import re
from pathlib import Path

from .constants import WINDOWS_RESERVED_NAMES

INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def validate_target_name(name: str, original_extension: str) -> list[str]:
    warnings: list[str] = []
    if not name or not name.strip():
        return ["文件名为空"]
    if INVALID_CHARS_RE.search(name):
        warnings.append("包含 Windows 非法字符")
    if name.endswith((" ", ".")):
        warnings.append("文件名不能以空格或点结尾")
    stem = Path(name).stem
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        warnings.append("文件名是 Windows 保留设备名")
    if Path(name).suffix.lower() != original_extension.lower():
        warnings.append("扩展名被修改")
    return warnings

