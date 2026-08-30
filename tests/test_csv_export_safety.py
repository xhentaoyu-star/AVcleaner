from __future__ import annotations

import pytest

from avcleaner.csv_export import safe_csv_cell


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\t=1", "  =1"])
def test_safe_csv_cell_neutralizes_formula_prefixes(value: str) -> None:
    assert safe_csv_cell(value).startswith("'")


def test_safe_csv_cell_keeps_ordinary_text_and_numbers() -> None:
    assert safe_csv_cell("ABP-123.mp4") == "ABP-123.mp4"
    assert safe_csv_cell(42) == 42
