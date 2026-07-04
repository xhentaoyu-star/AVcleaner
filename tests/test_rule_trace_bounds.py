from __future__ import annotations

from avcleaner.rules import MAX_REMOVED_TOKENS_PER_STEP, MAX_SUGGESTION_WARNINGS, MAX_TRACE_STEPS, suggest_name_with_trace


def test_trace_steps_keep_removed_tokens_bounded() -> None:
    filename = " ".join(f"ad{i}.com" for i in range(40)) + " ABP-123.mp4"

    suggestion = suggest_name_with_trace(filename)

    assert all(len(step.removed_tokens) <= MAX_REMOVED_TOKENS_PER_STEP for step in suggestion.trace)
    assert any("trace_truncated" in step.warnings for step in suggestion.trace)


def test_suggestion_warning_count_is_bounded() -> None:
    suggestion = suggest_name_with_trace("1080p.mp4")

    assert len(suggestion.warnings) <= MAX_SUGGESTION_WARNINGS


def test_normal_trace_step_count_stays_below_bound() -> None:
    suggestion = suggest_name_with_trace("[abc.com] FC2-PPV-4856696_1 WEB-DL.mp4")

    assert suggestion.trace
    assert len(suggestion.trace) <= MAX_TRACE_STEPS
    assert suggestion.trace[-1].after == suggestion.suggested_name
