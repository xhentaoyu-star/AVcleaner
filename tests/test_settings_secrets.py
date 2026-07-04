from __future__ import annotations

from avcleaner.database import connect, loads
from avcleaner.models import AppSettings
from avcleaner.secrets import InMemorySecretStore
from avcleaner.settings_store import get_settings, put_settings


def test_settings_do_not_persist_raw_llm_api_key_after_successful_secret_migration() -> None:
    store = InMemorySecretStore()
    settings = AppSettings()
    settings.llm.provider = "openai_compatible"
    settings.llm.api_key = "secret-value"

    saved = put_settings(settings, store)
    loaded = get_settings(store)

    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'app_settings'").fetchone()
    persisted = loads(row["value"])

    assert saved.llm.api_key == ""
    assert loaded.llm.api_key == ""
    assert persisted["llm"]["api_key"] == ""
    assert store.get_api_key("openai_compatible") == "secret-value"
