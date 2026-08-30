from __future__ import annotations

from collections.abc import Mapping


FORMULA_PREFIXES = ("=", "+", "-", "@")


def safe_csv_cell(value: object) -> object:
    if not isinstance(value, str) or not value:
        return value
    stripped = value.lstrip(" \t\r\n")
    if stripped.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def safe_csv_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: safe_csv_cell(value) for key, value in row.items()}
