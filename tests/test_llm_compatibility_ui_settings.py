from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "avcleaner" / "static" / "app.js"
INDEX_HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_llm_compatibility_modes_are_explained_in_ui() -> None:
    text = APP_JS.read_text(encoding="utf-8") + "\n" + INDEX_HTML.read_text(encoding="utf-8")

    for mode in [
        "openai_strict_json_schema",
        "prompt_json_compat",
        "claude_gateway_compat",
        "ollama_format_json",
    ]:
        assert mode in text

    for safety_phrase in [
        "does_not_bypass_validation",
        "requires_user_acceptance",
        "llm_never_executes_files",
    ]:
        assert safety_phrase in text
