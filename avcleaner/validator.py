from __future__ import annotations

from .validators import validate_filename


def validate_target_name(name: str, original_extension: str) -> list[str]:
    return [str(issue.code) for issue in validate_filename(name, original_extension)]

