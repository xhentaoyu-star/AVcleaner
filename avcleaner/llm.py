from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .models import LLMBatchResponse, LLMSuggestItem, LLMSuggestRequest, LLMSettings


LLM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_id": {"type": "string"},
                    "suggested_name": {"type": "string"},
                    "media_code": {"type": "string"},
                    "part_suffix": {"type": "string"},
                    "variant": {"type": "string"},
                    "removed_tokens": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "item_id",
                    "suggested_name",
                    "media_code",
                    "part_suffix",
                    "variant",
                    "removed_tokens",
                    "confidence",
                    "reason",
                    "warnings",
                ],
            },
        }
    },
    "required": ["suggestions"],
}


SYSTEM_PROMPT = (
    "You clean local media filenames. Return only JSON matching the schema. "
    "Do not invent metadata. Preserve the original extension. Prefer the media code, "
    "part suffix, and variant. Never return a full path."
)


def build_prompt(items: list[LLMSuggestItem], send_full_path: bool) -> str:
    payload = []
    for item in items:
        row: dict[str, Any] = {
            "item_id": item.id,
            "name": item.name,
            "extension": item.extension,
            "adjacent_names": item.adjacent_names[:8],
        }
        if send_full_path and item.path:
            row["path"] = item.path
        payload.append(row)
    return json.dumps({"items": payload}, ensure_ascii=False)


async def suggest_with_llm(request: LLMSuggestRequest, default_settings: LLMSettings) -> LLMBatchResponse:
    settings = request.settings or default_settings
    if settings.provider == "disabled":
        raise ValueError("LLM provider is disabled")
    if not settings.model:
        raise ValueError("LLM model is not configured")
    if settings.provider == "openai_compatible":
        return await _suggest_openai_compatible(request.items, settings)
    if settings.provider == "ollama":
        return await _suggest_ollama(request.items, settings)
    raise ValueError("Unsupported LLM provider")


async def _suggest_openai_compatible(items: list[LLMSuggestItem], settings: LLMSettings) -> LLMBatchResponse:
    import httpx

    if not settings.base_url:
        raise ValueError("OpenAI-compatible base URL is not configured")
    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    body = {
        "model": settings.model,
        "temperature": settings.temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(items, settings.send_full_path)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "avcleaner_suggestions",
                "strict": True,
                "schema": LLM_SCHEMA,
            },
        },
    }
    url = settings.base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"].get("content", "")
    return parse_llm_payload(content)


async def _suggest_ollama(items: list[LLMSuggestItem], settings: LLMSettings) -> LLMBatchResponse:
    import httpx

    base_url = settings.base_url.rstrip("/") if settings.base_url else "http://127.0.0.1:11434"
    body = {
        "model": settings.model,
        "stream": False,
        "format": LLM_SCHEMA,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_prompt(items, settings.send_full_path)},
        ],
        "options": {"temperature": settings.temperature},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{base_url}/api/chat", json=body)
        response.raise_for_status()
    data = response.json()
    content = data.get("message", {}).get("content", "")
    return parse_llm_payload(content)


def parse_llm_payload(content: str | dict[str, Any]) -> LLMBatchResponse:
    try:
        raw = content if isinstance(content, dict) else json.loads(content)
        return LLMBatchResponse.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("LLM returned invalid structured output") from exc

