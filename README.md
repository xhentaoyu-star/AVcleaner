# AVcleaner

AVcleaner is a local Windows desktop-style app for safely cleaning downloaded media filenames before they enter a media library. It focuses on local preview, manual review, execution history, rollback, and reports.

Current version: `0.8.0`.

AVcleaner intentionally does not scrape metadata, download covers, generate NFO files, move files into a final media library, organize actor/studio/category folders, or integrate with OpenAver databases.

## What v0.8.0 Adds

- Default workbench mode is now a simple daily-use view. Scan ID, Plan ID, full hash, raw JSON, Trace, endpoint flags, runtime diagnostics, and internal IDs stay out of the visible workflow.
- Advanced diagnostics remain available through the hidden local shortcut `Ctrl+Shift+D`. This local UI state is not exported in settings and is not sent to LLM providers.
- First-use safety help is now a compact one-line safety bar with expandable details instead of a large block.
- Summary cards use progressive disclosure: total files, rename, quarantine, selected, and blocking stay visible; warning, review, manual edit, and sidecar cards appear only when relevant in simple mode.
- The execution report appears only after an execution starts or completes. Empty run_id/status/result boxes are no longer shown before execution.
- Settings show human summaries first. Raw LLM test JSON, settings import/export JSON, capability flags, and diagnostics JSON are collapsed under advanced/debug sections.

## What v0.7.5 Added

- Fixed-resolution desktop workbench layout optimized for 1440 x 900, with a minimum supported viewport of 1280 x 760. Very wide screens keep the content capped instead of stretching endlessly.
- Strong module zones: top navigation, command bar, KPI strip, compact review table, right-side detail stack, compact execution module, and bottom local-status bar.
- Main review table now keeps long names, paths, Trace, AI details, and raw Debug data out of table cells. Short summaries stay in the table; full details live in the right panel.
- Right-side detail stack now carries item details, optional AI review, collapsed Debug information, and quick local actions.
- Compact execution module shows selected count, rename/quarantine/skip/warning pills, execution summary, explicit confirmation, and recent run result.
- Cleaner icon-based UI using a minimal vendored Tabler Icons regular outline subset. No CDN, no external icon dependency, and secondary actions use compact accessible icon buttons.
- Reproducible icon registry and sprite generation with `tools/build_icon_sprite.py --check`.
- Two-pane review workbench: compact table on the left, full detail/debug panel on the right.
- Settings subnav for LLM, rules, import/export, and diagnostics instead of four equal-weight panels.
- Configurable local quarantine folder. The default quarantine location is AVcleaner's own runtime `quarantine` directory, not the selected source folder.
- Short technical IDs in the main status strip, with full values still available in tooltips/detail context.
- Immediate local feedback for analysis, AI preview fallback, validation, manual edits, exports, execution, rollback, settings, LLM tests, and diagnostics.
- Responsive preview table with stable columns, sticky header, truncated summaries, compact badges, and internal scrolling instead of page overflow.
- Detail panel for full item context: original path, final name, action/source, issue codes, trace, sidecar metadata, LLM details, and debug JSON.
- Unified analysis workflow: choose a folder, choose preview mode, analyze once, review/edit final names, then execute selected.
- Rule Preview mode for deterministic local rules.
- AI Smart Preview mode when LLM is configured. If LLM is not configured, the AI mode is hidden from the main workflow.
- AI suggestions update the preview `target_name` only after canonical schema validation and normal filename validators pass. They never execute files.
- Final suggested filenames remain manually editable in both Rule and AI modes.
- Native PyWebView folder picker in desktop mode, with safe browser fallback text.
- Local last-folder memory and recent folders. Selecting a recent folder only fills the path input; it does not auto-scan.
- Segment suffix preservation for `-A/-B/-C` and numeric parts such as `-1/-2`.
- De-duplicated review information so repeated stable codes are shown once.

## Daily Workflow

1. Choose a folder, preferably with the desktop folder button.
2. Choose Rule Preview or AI Smart Preview.
3. Click the primary preview button. AVcleaner scans, creates a persisted plan, validates it, and fills the preview table.
4. Review the table. The final filename column is editable.
5. Select safe items or manually select confirmed rows.
6. View the execution summary, then execute selected items with confirmation.
7. Read the local execution report.
8. Use History for run details, rollback preview, rollback execution, or JSON/CSV reports.

AI mode is preview-only. Invalid AI suggestions fall back to the rule result and show stable error state. Manual edits override preview suggestions.

## Safety Model

- Scan and preview never rename, quarantine, delete, or move files.
- 隔离不是永久删除；隔离文件可以通过历史回滚恢复。
- Execution requires persisted `plan_id`, matching `plan_hash`, selected item ids, and explicit `confirm: true`.
- Execution never trusts frontend-supplied file paths.
- Existing files are never overwritten.
- New quarantined files are stored under AVcleaner's runtime quarantine folder by default, or under the custom quarantine folder configured in Settings.
- Rollback never overwrites restore targets.
- LLM endpoints never execute files and never bypass Pydantic/schema/validator checks.
- Cloud LLM payloads send filenames only by default, not full paths.
- API keys, Authorization headers, keyring secrets, raw LLM payloads, and full local media paths are not exposed in reports or diagnostics.
- Legacy `POST /api/execute` remains disabled with `error_code=legacy_execute_disabled`.
- Generic `POST /api/llm/suggest` remains disabled with `error_code=legacy_llm_suggest_disabled`.

## Runtime Data

- Source/AppData mode stores data under `%LOCALAPPDATA%\AVcleaner` unless `AVCLEANER_DATA_DIR` overrides it.
- Portable mode is enabled by `--portable` or a `portable.flag` next to the executable. Data is stored beside the executable under `data`, `logs`, and `quarantine`.
- The quarantine folder can be changed in Settings > Rules. Leave it empty to use the default AVcleaner `quarantine` directory. AVcleaner no longer creates a new quarantine folder inside the selected source folder for new executions.
- Diagnostics redact local media paths and secrets. Recent folders and folder-picker state are local workflow data and are not included in settings export by default.

## Quick Start

```powershell
cd L:\1\AVcleaner
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8765
```

Desktop wrapper with native folder picker:

```powershell
.\.venv\Scripts\python.exe -m avcleaner.desktop
```

Development checks:

```powershell
.\scripts\test.ps1
.\scripts\corpus.ps1
.\scripts\check.ps1
```

This machine may have more than one Python installation. Use the project venv commands or helper scripts instead of bare python for project checks.

## Local daily workflow

The v0.8.0 local daily workflow is the same workflow described above: choose a folder, choose Rule Preview or AI Smart Preview, generate one validated preview, review/edit final names, execute selected items, then inspect reports or rollback from History.

The v0.8.0 workbench simplification is local-only: the sidebar shell, hidden advanced diagnostics shortcut, compact safety help, progressive disclosure, toast/status feedback, compact table rows, and the detail stack do not change execution rules or LLM safety. The backend remains authoritative for validation, selection, `plan_hash`, execution, and rollback.

Debug mode is where technical details live: full Scan/Plan IDs, full `plan_hash`, Trace, raw sanitized LLM test results, diagnostics JSON, API capability flags, runtime/database status, and internal item/run IDs. Simple mode keeps those details out of the main workflow.

Recommended desktop window size is 1440 x 900 or larger. The desktop wrapper opens at 1440 x 900 and enforces a 1280 x 760 minimum. Browser mode is optimized for desktop width; below the minimum, the page scrolls instead of crushing table columns.

UI labels keep the important safety words visible: 阻止 means the item cannot execute, 警告 means review before execution, and 需复核 means the user should confirm the result before selecting it.

Compatibility mode does not bypass validation. It only changes how LLM JSON is requested or parsed before the same strict schema and filename validators run.

Packaging checks, when a build exists:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\packaging\build_portable.ps1
.\scripts\check_artifact.ps1 .\dist\AVcleaner
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner -RunTempExecution
.\packaging\create_release_zip.ps1 -SmokeTested
.\scripts\check_artifact.ps1 .\release\AVcleaner-v0.8.0-portable-win-x64.zip
.\scripts\smoke_release_zip.ps1 .\release\AVcleaner-v0.8.0-portable-win-x64.zip
Get-FileHash .\release\AVcleaner-v0.8.0-portable-win-x64.zip -Algorithm SHA256
```

## API Flow

```text
POST /api/analyze
POST /api/scan
POST /api/plans
GET  /api/plans/{plan_id}
POST /api/plans/{plan_id}/validate
PATCH /api/plans/{plan_id}/items/{item_id}
PATCH /api/plans/{plan_id}/selection
POST /api/plans/{plan_id}/execution-summary
GET  /api/plans/{plan_id}/export.json
GET  /api/plans/{plan_id}/export.csv
POST /api/plans/{plan_id}/execute
GET  /api/runs
GET  /api/runs/{run_id}
POST /api/runs/{run_id}/rollback-preview
POST /api/runs/{run_id}/rollback
GET  /api/runs/{run_id}/export.json
GET  /api/runs/{run_id}/export.csv
GET  /api/recent-folders
POST /api/recent-folders
DELETE /api/recent-folders
GET  /api/folder-picker-state
PUT  /api/folder-picker-state
POST /api/rules/test
GET  /api/rules/corpus-report
GET  /api/settings/export
POST /api/settings/import
```
