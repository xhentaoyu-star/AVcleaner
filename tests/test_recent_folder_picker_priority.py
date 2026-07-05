from __future__ import annotations

from pathlib import Path


def test_frontend_folder_picker_initial_dir_priority_is_stable() -> None:
    source = (Path(__file__).resolve().parents[1] / "avcleaner" / "static" / "app.js").read_text(encoding="utf-8")
    function_start = source.index("function folderPickerInitialDir")
    snippet = source[function_start : source.index("async function chooseFolder", function_start)]

    current_index = snippet.index('$("#rootPath")?.value.trim()')
    last_dialog_index = snippet.index("state.folderPickerState?.last_folder_dialog_dir")
    recent_index = snippet.index("state.recentFolders?.[0]?.path")

    assert current_index < last_dialog_index < recent_index
