from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "avcleaner" / "templates" / "index.html"


def test_workbench_declares_major_zones() -> None:
    html = HTML.read_text(encoding="utf-8")

    for zone in ["sidebar", "command", "kpi", "review-workbench", "execution", "detail-stack", "statusbar"]:
        assert f'data-zone="{zone}"' in html
    for tab in ["workspace", "trash", "history", "settings"]:
        assert f'data-tab="{tab}"' in html
    assert 'class="sidebar-search"' in html
    assert 'class="topbar"' not in html
    assert 'class="nav-tabs"' not in html
    assert 'class="bottom-status-bar"' in html


def test_command_bar_uses_compact_status_with_debug_technical_fields() -> None:
    html = HTML.read_text(encoding="utf-8")

    for marker in ["scanId", "planId", "planState", "planHash", "blockingCount", "statusSelectedCount", "previewModeStatus"]:
        assert f'id="{marker}"' in html
    status = html[html.index('class="status-strip compact-status-strip"') : html.index('class="recent-row"')]
    assert 'id="operationStatusChip"' in status
    assert 'data-debug-only data-debug-field="scan-id"' in status
    assert 'data-debug-only data-debug-field="plan-id"' in status
    assert 'data-debug-only data-debug-field="plan-hash"' in status
