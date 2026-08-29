from __future__ import annotations

import warnings
from pathlib import Path

import pytest
from starlette.exceptions import StarletteDeprecationWarning

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=StarletteDeprecationWarning,
    module="fastapi.testclient",
)

from fastapi.testclient import TestClient

from avcleaner.app import API_TOKEN, app


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AVCLEANER_DATA_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AVCLEANER_SECRET_STORE", "env")


@pytest.fixture
def client():
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-AVCleaner-Token": API_TOKEN}


def make_file(root: Path, name: str, content: bytes = b"video") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
