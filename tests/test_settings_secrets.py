from __future__ import annotations

import pytest

from avcleaner.database import connect, loads
from avcleaner.errors import AppError
from avcleaner.models import AppSettings
from avcleaner.secrets import InMemorySecretStore
from avcleaner.settings_store import get_settings, put_settings


class BrokenSecretStore:
    def set_api_key(self, provider: str, api_key: str) -> None:
        raise RuntimeError("secret backend unavailable")

    def get_api_key(self, provider: str) -> str:
        raise RuntimeError("secret backend unavailable")

    def delete_api_key(self, provider: str) -> None:
        raise RuntimeError("secret backend unavailable")


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


def test_settings_fail_closed_when_secret_store_is_unavailable() -> None:
    settings = AppSettings()
    settings.llm.provider = "openai_compatible"
    settings.llm.api_key = "must-not-reach-database"

    with pytest.raises(AppError) as error:
        put_settings(settings, BrokenSecretStore())

    assert error.value.error_code == "secret_store_unavailable"
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'app_settings'").fetchone()
    assert row is None or "must-not-reach-database" not in row["value"]


def test_disabled_provider_discards_supplied_api_key() -> None:
    settings = AppSettings()
    settings.llm.provider = "disabled"
    settings.llm.api_key = "irrelevant-secret"

    saved = put_settings(settings, BrokenSecretStore())

    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = 'app_settings'").fetchone()
    persisted = loads(row["value"])
    assert saved.llm.api_key == ""
    assert persisted["llm"]["api_key"] == ""
