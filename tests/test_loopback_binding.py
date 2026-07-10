from __future__ import annotations

import sys

import pytest

import run as run_module
from avcleaner import desktop
from avcleaner.runtime import is_loopback_host


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.0.0.2", "::1"])
def test_loopback_hosts_are_allowed(host: str) -> None:
    assert is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "example.local"])
def test_non_loopback_hosts_are_rejected(host: str) -> None:
    assert is_loopback_host(host) is False


def test_server_rejects_lan_binding_even_with_legacy_override(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["run.py", "--host", "192.168.1.20", "--dev-allow-lan"])

    with pytest.raises(SystemExit):
        run_module.main()
    assert "host_not_allowed" in capsys.readouterr().err


def test_desktop_rejects_lan_binding_even_with_legacy_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["desktop.py", "--host", "192.168.1.20", "--dev-allow-lan"])

    with pytest.raises(SystemExit, match="host_not_allowed"):
        desktop.main()
