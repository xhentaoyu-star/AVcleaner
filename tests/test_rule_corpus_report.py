from __future__ import annotations

from tools.rule_corpus_report import build_report, format_report


def test_rule_corpus_report_passes_current_fixtures() -> None:
    report = build_report()

    assert report.total_cases > 0
    assert report.total_failures == 0
    assert report.recognized_media_code_cases > 0
    assert report.sidecar_cases > 0
    assert report.language_suffix_cases > 0
    assert report.associated_file_cases > 0
    assert "Rule Corpus Report" in format_report(report)
    assert "Sidecar cases:" in format_report(report)
