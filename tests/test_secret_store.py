from __future__ import annotations

from avcleaner.models import AppSettings
from avcleaner.secrets import InMemorySecretStore
from avcleaner.settings_store import effective_llm_api_key, put_settings


def test_in_memory_secret_store_roundtrip() -> None:
    store = InMemorySecretStore()
    store.set_api_key("ollama", "secret")
    assert store.get_api_key("ollama") == "secret"
    store.delete_api_key("ollama")
    assert store.get_api_key("ollama") is None


def test_put_settings_moves_api_key_to_secret_store() -> None:
    store = InMemorySecretStore()
    settings = AppSettings()
    settings.llm.provider = "openai_compatible"
    settings.llm.api_key = "secret"

    saved = put_settings(settings, store)

    assert saved.llm.api_key == ""
    assert effective_llm_api_key(saved, store) == "secret"
