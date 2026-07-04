from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "filenames"
REQUIRED_KEYS = {
    "input",
    "expected_suggested_name",
    "expected_code",
    "expected_part_suffix",
    "expected_variant",
    "should_review",
    "expected_warning_codes",
}
LOCAL_PATH_RE = re.compile(r"(?i)(?:[A-Z]:\\|/home/|\\\\[^\\]+\\[^\\]+|C:\\Users|L:\\)")
INVALID_WINDOWS_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def fixture_files() -> list[Path]:
    return sorted(FIXTURE_ROOT.glob("*.json"))


def load_rows(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", fixture_files(), ids=lambda path: path.name)
def test_fixture_items_have_required_keys(path: Path) -> None:
    for row in load_rows(path):
        assert REQUIRED_KEYS.issubset(row.keys())
        if "notes" in row:
            assert isinstance(row["notes"], str)


@pytest.mark.parametrize("path", fixture_files(), ids=lambda path: path.name)
def test_fixture_items_do_not_contain_full_local_paths(path: Path) -> None:
    for row in load_rows(path):
        payload = json.dumps(row, ensure_ascii=False)
        assert not LOCAL_PATH_RE.search(payload)


@pytest.mark.parametrize("path", fixture_files(), ids=lambda path: path.name)
def test_expected_suggested_names_are_windows_filename_safe(path: Path) -> None:
    for row in load_rows(path):
        assert not INVALID_WINDOWS_CHARS_RE.search(row["expected_suggested_name"])


def test_false_positive_fixtures_expect_no_media_code() -> None:
    for row in load_rows(FIXTURE_ROOT / "false_positives.json"):
        assert row["expected_code"] is None


@pytest.mark.parametrize("name", ["junk_files.json", "associated_files.json"])
def test_junk_and_associated_fixtures_are_not_execution_tests(name: str) -> None:
    for row in load_rows(FIXTURE_ROOT / name):
        assert "source_path" not in row
        assert "target_path" not in row
        assert "plan_id" not in row
        assert row.get("expected_action") in {"keep", "quarantine"}
