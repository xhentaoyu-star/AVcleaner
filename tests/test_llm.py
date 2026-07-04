from __future__ import annotations

import json

from avcleaner.llm import build_prompt, parse_llm_payload
from avcleaner.models import LLMSuggestItem


def test_llm_payload_validation() -> None:
    payload = {
        "suggestions": [
            {
                "item_id": "1",
                "suggested_name": "ABP-123.mp4",
                "media_code": "ABP-123",
                "part_suffix": "",
                "variant": "",
                "removed_tokens": ["hhd800.com"],
                "confidence": 0.91,
                "reason": "detected code",
                "warnings": [],
            }
        ]
    }
    parsed = parse_llm_payload(json.dumps(payload))
    assert parsed.suggestions[0].suggested_name == "ABP-123.mp4"


def test_llm_prompt_omits_path_by_default() -> None:
    item = LLMSuggestItem(
        id="1",
        name="hhd800.com@ABP-123.mp4",
        extension=".mp4",
        adjacent_names=["ABP-123.srt"],
        path="L:\\secret\\hhd800.com@ABP-123.mp4",
    )
    prompt = build_prompt([item], send_full_path=False)

    assert "hhd800.com@ABP-123.mp4" in prompt
    assert "L:\\secret" not in prompt

