from __future__ import annotations

from .constants import DEFAULT_EXCLUDE_DIRS
from .database import load_setting, save_setting
from .models import AppSettings

SETTINGS_KEY = "app_settings"


def default_settings() -> AppSettings:
    settings = AppSettings()
    settings.exclude_dirs = sorted(DEFAULT_EXCLUDE_DIRS)
    return settings


def get_settings() -> AppSettings:
    raw = load_setting(SETTINGS_KEY)
    if raw is None:
        return default_settings()
    return AppSettings.model_validate(raw)


def put_settings(settings: AppSettings) -> AppSettings:
    save_setting(SETTINGS_KEY, settings.model_dump(mode="json"))
    return settings

