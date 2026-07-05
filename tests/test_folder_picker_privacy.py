from __future__ import annotations

from pathlib import Path


def test_last_folder_dialog_dir_not_in_settings_export_or_diagnostics(
    client,
    auth_headers: dict[str, str],
    tmp_path: Path,
) -> None:
    secret_like_path = str(tmp_path / "private-media-root")
    response = client.put(
        "/api/folder-picker-state",
        headers=auth_headers,
        json={"last_folder_dialog_dir": secret_like_path},
    )
    assert response.status_code == 200

    settings_export = client.get("/api/settings/export", headers=auth_headers)
    diagnostics = client.get("/api/diagnostics", headers=auth_headers)

    assert settings_export.status_code == 200
    assert diagnostics.status_code == 200
    assert secret_like_path not in settings_export.text
    assert secret_like_path not in diagnostics.text
