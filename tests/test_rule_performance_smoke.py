from __future__ import annotations

from avcleaner.rules import MAX_TRACE_STEPS, suggest_name_with_trace


def test_rule_pipeline_handles_moderate_synthetic_batch_without_side_effects() -> None:
    filenames = [
        f"hhd800.com@FC2-PPV-{1000000 + index}_{(index % 3) + 1} 1080p.mp4"
        if index % 2 == 0
        else f"[ad.com] HEYZO-{1000 + index} WEB-DL.mkv"
        for index in range(1000)
    ]

    suggestions = [suggest_name_with_trace(filename) for filename in filenames]

    assert len(suggestions) == 1000
    assert all(suggestion.trace for suggestion in suggestions)
    assert all(len(suggestion.trace) <= MAX_TRACE_STEPS for suggestion in suggestions)
    assert all(suggestion.media_code for suggestion in suggestions)
