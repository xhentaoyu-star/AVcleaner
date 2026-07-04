from __future__ import annotations

from avcleaner.rule_corpus import build_report, format_report, report_response_payload
from tools.rule_corpus_report import main


def test_shared_corpus_report_payload_matches_report() -> None:
    report = build_report()
    payload = report_response_payload(report)

    assert payload["summary"]["total_cases"] == report.total_cases
    assert payload["summary"]["total_failures"] == report.total_failures
    assert payload["by_fixture"]
    assert "Rule Corpus Report" in format_report(report)


def test_cli_uses_shared_corpus_logic() -> None:
    assert main([]) == 0
