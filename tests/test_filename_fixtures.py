from __future__ import annotations

import json
from pathlib import Path

import pytest

from avcleaner.models import PlanRequest, ScanRequest
from avcleaner.planner import create_plan
from avcleaner.repository import create_scan
from avcleaner.scanner import scan_files
from avcleaner.validator import validate_target_name

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "filenames"


def load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("row", load_fixture("invalid_windows_names.json"))
def test_invalid_windows_name_fixtures(row: dict) -> None:
    assert row["expected_issue"] in validate_target_name(row["input"], Path(row["input"]).suffix or ".mp4")


@pytest.mark.parametrize("row", load_fixture("junk_files.json"))
def test_junk_file_fixtures(row: dict, tmp_path: Path) -> None:
    path = tmp_path / row["input"]
    path.write_bytes(b"" if row["input"] == "empty.txt" else b"junk")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert plan.items[0].action == row["expected_action"]


@pytest.mark.parametrize("row", load_fixture("false_positives.json"))
def test_false_positive_fixtures_go_to_review(row: dict, tmp_path: Path) -> None:
    (tmp_path / row["input"]).write_bytes(b"video")
    scan = create_scan(ScanRequest(root_path=str(tmp_path)), scan_files(ScanRequest(root_path=str(tmp_path))))
    plan = create_plan(PlanRequest(scan_id=scan.scan_id))

    assert plan.items[0].requires_review is row["should_review"]
    assert plan.items[0].action == "review"
    assert plan.items[0].media_code == (row["expected_code"] or "")
