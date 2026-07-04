from __future__ import annotations

import os
from typing import Protocol


class SecretStore(Protocol):
    def get_api_key(self, provider: str) -> str | None: ...
    def set_api_key(self, provider: str, value: str) -> None: ...
    def delete_api_key(self, provider: str) -> None: ...


class InMemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get_api_key(self, provider: str) -> str | None:
        return self._values.get(provider)

    def set_api_key(self, provider: str, value: str) -> None:
        self._values[provider] = value

    def delete_api_key(self, provider: str) -> None:
        self._values.pop(provider, None)


class EnvSecretStore:
    def get_api_key(self, provider: str) -> str | None:
        key = f"AVCLEANER_{provider.upper()}_API_KEY"
        return os.environ.get(key)

    def set_api_key(self, provider: str, value: str) -> None:
        os.environ[f"AVCLEANER_{provider.upper()}_API_KEY"] = value

    def delete_api_key(self, provider: str) -> None:
        os.environ.pop(f"AVCLEANER_{provider.upper()}_API_KEY", None)


class KeyringSecretStore:
    service_name = "AVcleaner"

    def get_api_key(self, provider: str) -> str | None:
        import keyring

        return keyring.get_password(self.service_name, provider)

    def set_api_key(self, provider: str, value: str) -> None:
        import keyring

        keyring.set_password(self.service_name, provider, value)

    def delete_api_key(self, provider: str) -> None:
        import keyring

        try:
            keyring.delete_password(self.service_name, provider)
        except Exception:
            return


def get_secret_store() -> SecretStore:
    if os.environ.get("AVCLEANER_SECRET_STORE") == "env":
        return EnvSecretStore()
    try:
        import keyring  # noqa: F401

        return KeyringSecretStore()
    except Exception:
        return EnvSecretStore()
