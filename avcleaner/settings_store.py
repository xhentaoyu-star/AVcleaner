from __future__ import annotations

from .constants import DEFAULT_EXCLUDE_DIRS
from .database import load_setting, save_setting
from .models import AppSettings, SettingsImportResponse
from .secrets import SecretStore, get_secret_store

SETTINGS_KEY = "app_settings"


def default_settings() -> AppSettings:
    settings = AppSettings()
    settings.exclude_dirs = sorted(DEFAULT_EXCLUDE_DIRS)
    return settings


def _migrate_api_key(settings: AppSettings, store: SecretStore) -> AppSettings:
    api_key = settings.llm.api_key
    if not api_key or settings.llm.provider == "disabled":
        return settings
    provider = settings.llm.provider
    try:
        store.set_api_key(provider, api_key)
        if store.get_api_key(provider) == api_key:
            cleaned = settings.model_copy(update={"llm": settings.llm.model_copy(update={"api_key": ""})})
            save_setting(SETTINGS_KEY, cleaned.model_dump(mode="json"), cleaned.schema_version)
            return cleaned
    except Exception:
        return settings
    return settings


def get_settings(store: SecretStore | None = None) -> AppSettings:
    raw = load_setting(SETTINGS_KEY)
    if raw is None:
        return default_settings()
    settings = AppSettings.model_validate(raw)
    return _migrate_api_key(settings, store or get_secret_store())


def put_settings(settings: AppSettings, store: SecretStore | None = None) -> AppSettings:
    secret_store = store or get_secret_store()
    api_key = settings.llm.api_key
    cleaned = settings
    if api_key and settings.llm.provider != "disabled":
        try:
            secret_store.set_api_key(settings.llm.provider, api_key)
            if secret_store.get_api_key(settings.llm.provider) == api_key:
                cleaned = settings.model_copy(update={"llm": settings.llm.model_copy(update={"api_key": ""})})
        except Exception:
            cleaned = settings
    save_setting(SETTINGS_KEY, cleaned.model_dump(mode="json"), cleaned.schema_version)
    return cleaned


def effective_llm_api_key(settings: AppSettings, store: SecretStore | None = None) -> str:
    if settings.llm.api_key:
        return settings.llm.api_key
    if settings.llm.provider == "disabled":
        return ""
    return (store or get_secret_store()).get_api_key(settings.llm.provider) or ""


def sanitized_settings_payload(settings: AppSettings) -> dict:
    payload = settings.model_dump(mode="json")
    payload.setdefault("llm", {}).pop("api_key", None)
    return payload


def _drop_imported_secrets(raw_settings: dict) -> tuple[dict, list[str]]:
    payload = dict(raw_settings)
    warnings: list[str] = []
    if isinstance(payload.get("llm"), dict) and "api_key" in payload["llm"]:
        payload["llm"] = dict(payload["llm"])
        payload["llm"].pop("api_key", None)
        warnings.append("llm_api_key_ignored")
    return payload, warnings


def preview_settings_import(raw_settings: dict, *, dry_run: bool) -> SettingsImportResponse:
    payload, warnings = _drop_imported_secrets(raw_settings)
    imported = AppSettings.model_validate(payload)
    current = get_settings()
    before = sanitized_settings_payload(current)
    after = sanitized_settings_payload(imported)
    changes = [key for key in sorted(after) if before.get(key) != after.get(key)]
    if not dry_run:
        saved = put_settings(imported)
        after = sanitized_settings_payload(saved)
    return SettingsImportResponse(
        dry_run=dry_run,
        applied=not dry_run,
        settings=after,
        changes=changes,
        warnings=warnings,
    )
