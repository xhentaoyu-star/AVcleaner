from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .rules import suggest_name_with_trace
from .sidecars import classify_sidecar_type

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "filenames"


@dataclass
class FixtureFileReport:
    name: str
    total: int = 0
    passed: int = 0
    failed: int = 0


@dataclass
class CorpusReport:
    total_cases: int = 0
    total_failures: int = 0
    recognized_media_code_cases: int = 0
    sidecar_cases: int = 0
    language_suffix_cases: int = 0
    associated_file_cases: int = 0
    false_positive_failures: int = 0
    requires_review_cases: int = 0
    warnings: Counter[str] = field(default_factory=Counter)
    by_file: list[FixtureFileReport] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def load_fixture(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def expectation_failures(path: Path, row: dict[str, Any]) -> list[str]:
    suggestion = suggest_name_with_trace(row["input"])
    failures: list[str] = []
    checks = {
        "expected_suggested_name": suggestion.suggested_name,
        "expected_code": suggestion.media_code,
        "expected_part_suffix": suggestion.part_suffix,
        "expected_variant": suggestion.variant,
        "expected_language_suffix": suggestion.language_suffix,
        "should_review": suggestion.requires_review,
    }
    for key, actual in checks.items():
        if key in row and row.get(key) != actual:
            failures.append(f"{path.name}:{row['input']}: {key} expected={row.get(key)!r} actual={actual!r}")
    for warning in row.get("expected_warning_codes", []):
        if warning not in suggestion.warnings:
            failures.append(f"{path.name}:{row['input']}: missing warning {warning!r}")
    return failures


def build_report(fixture_root: Path = FIXTURE_ROOT) -> CorpusReport:
    report = CorpusReport()
    for path in sorted(fixture_root.glob("*.json")):
        rows = load_fixture(path)
        file_report = FixtureFileReport(name=path.name, total=len(rows))
        for row in rows:
            suggestion = suggest_name_with_trace(row["input"])
            failures = expectation_failures(path, row)
            report.total_cases += 1
            extension = Path(row["input"]).suffix
            if classify_sidecar_type(extension):
                report.sidecar_cases += 1
            if row.get("expected_language_suffix") or suggestion.language_suffix:
                report.language_suffix_cases += 1
            if path.name in {"associated_files.json", "subtitle_language_suffixes.json"}:
                report.associated_file_cases += 1
            if suggestion.media_code:
                report.recognized_media_code_cases += 1
            if suggestion.requires_review:
                report.requires_review_cases += 1
            report.warnings.update(suggestion.warnings)
            if path.name == "false_positives.json" and suggestion.media_code:
                report.false_positive_failures += 1
            if failures:
                file_report.failed += 1
                report.failures.extend(failures)
            else:
                file_report.passed += 1
        report.total_failures += file_report.failed
        report.by_file.append(file_report)
    return report


def format_report(report: CorpusReport) -> str:
    lines = [
        "Rule Corpus Report",
        f"Total cases: {report.total_cases}",
        f"Total failures: {report.total_failures}",
        f"Recognized media_code cases: {report.recognized_media_code_cases}",
        f"Sidecar cases: {report.sidecar_cases}",
        f"Language suffix preservation cases: {report.language_suffix_cases}",
        f"Associated file cases: {report.associated_file_cases}",
        f"False-positive failures: {report.false_positive_failures}",
        f"Requires review cases: {report.requires_review_cases}",
        "",
        "By fixture:",
    ]
    for item in report.by_file:
        lines.append(f"  {item.name}: {item.passed}/{item.total} passed, {item.failed} failed")
    lines.append("")
    lines.append("Warnings:")
    if report.warnings:
        for code, count in sorted(report.warnings.items()):
            lines.append(f"  {code}: {count}")
    else:
        lines.append("  none")
    if report.failures:
        lines.append("")
        lines.append("Failures:")
        lines.extend(f"  {failure}" for failure in report.failures)
    return "\n".join(lines)


def report_response_payload(report: CorpusReport) -> dict[str, Any]:
    return {
        "summary": {
            "total_cases": report.total_cases,
            "total_failures": report.total_failures,
            "recognized_media_code_cases": report.recognized_media_code_cases,
            "sidecar_cases": report.sidecar_cases,
            "language_suffix_preservation_cases": report.language_suffix_cases,
            "associated_file_cases": report.associated_file_cases,
            "false_positive_failures": report.false_positive_failures,
            "requires_review_cases": report.requires_review_cases,
        },
        "by_fixture": [
            {"name": item.name, "total": item.total, "passed": item.passed, "failed": item.failed}
            for item in report.by_file
        ],
        "failures": report.failures,
    }
