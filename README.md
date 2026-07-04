# AVcleaner

AVcleaner is a local Windows desktop-style web app for cleaning downloaded media
file names before they enter a media library. It focuses on safe local file
renaming, junk-file quarantine, preview, confirmation, execution history, and
rollback.

Current version: `0.6.1`.

It intentionally does not scrape metadata, download covers, generate NFO files,
or organize a final media library. Those jobs belong to OpenAver.

## Features

- Local FastAPI + PyWebView architecture.
- Rule-based media code extraction and filename normalization.
- Explainable rule trace for rule-generated rename suggestions.
- Golden filename corpus under `tests/fixtures/filenames/` for FC2, HEYZO,
  428SUKE, numeric underscore codes, ad/noise cleanup, part suffixes, variants,
  false positives, junk files, and associated files.
- Rule corpus report CLI for checking fixture pass/fail counts and warning
  distribution.
- Versioned RuleSettings for safe rule tuning, including output template,
  ad-domain cleanup, noise token cleanup, part/variant preservation, sidecar
  language preservation, and review threshold.
- Token-protected settings import/export. Exports do not include API keys, and
  imports ignore API keys.
- Token-protected corpus report endpoint for the same fixture checks used by
  the CLI.
- Manual review workflow with persisted selection state, review buckets,
  safe-item selection, inline `target_name` edits, execution summaries, and
  JSON/CSV plan export.
- Review-only LLM suggestions with payload privacy preview, provider
  compatibility modes, deterministic suggestion cache, explicit accept/reject
  workflow, stale-suggestion checks, and manual-edit conflict protection.
- Sidecar awareness for subtitles, images, and NFO files.
- Subtitle language suffix preservation, for example `.zh.srt`, `.chs.ass`,
  `.zh-CN.srt`, and `.zh-Hans.srt`.
- Associated-file preview grouping by detected media code; sidecar rename
  suggestions are visible but not selected by default.
- LLM provider interface for strict OpenAI-compatible JSON Schema, prompt JSON
  compatibility gateways such as Claude/Anthropic middle layers, and Ollama.
- Preview-first workflow with conflict and safety validation.
- SQLite run history.
- Quarantine area with rollback instead of permanent deletion.
- Windows portable packaging scripts, release zip/checksum generation, artifact
  manifest, artifact sanity checks, packaged smoke tests, packaged temp
  execution smoke, and a token-protected health endpoint.

## Release candidate GUI workflow

The v0.6.1 release candidate GUI is organized for review clarity:

1. Choose a folder and scan.
2. Generate preview. This still does not touch files.
3. Review and select. Stable backend codes are kept in the data, while the GUI
   shows Chinese labels, explanations, and suggested actions.
4. Open LLM suggestions only when needed. The LLM section is collapsed by
   default and appears after a plan exists.
5. Show execution summary, then execute selected items with explicit
   confirmation.
6. Use history to roll back a run when needed.

`阻止` means AVcleaner will not execute that item. `警告` means review before
executing. `需复核` means the rule result is visible, but the user should make
the decision. `隔离` means 隔离不是永久删除; quarantined files can be restored
through rollback. Associated files such as subtitles, images, and NFO files are
visible in the same workflow but are not selected by default.

## Quick Start

```powershell
cd L:\1\AVcleaner
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py --host 127.0.0.1 --port 8765
```

This machine has more than one Python installation. Use the project venv
commands or helper scripts instead of bare python for project checks:

```powershell
.\scripts\run.ps1
.\scripts\test.ps1
.\scripts\corpus.ps1
.\scripts\check.ps1
```

Open `http://127.0.0.1:8765` in a browser.

Desktop wrapper:

```powershell
.\.venv\Scripts\python.exe -m avcleaner.desktop
```

## Runtime Data

AVcleaner supports two distribution modes:

- AppData mode is the default for installed or source runs. Data is stored under
  `%LOCALAPPDATA%\AVcleaner` on Windows.
- Portable mode is enabled by `--portable` or a `portable.flag` file next to the
  executable. Data is stored beside the executable under `data`, `logs`, and
  `quarantine`.

Development tests may override the data directory with `AVCLEANER_DATA_DIR`.
The packaged app binds to `127.0.0.1` by default and chooses the next available
local port if the preferred port is occupied.

Build a portable package:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\packaging\build_portable.ps1
.\scripts\check_artifact.ps1 .\dist\AVcleaner
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner
.\scripts\smoke_packaged.ps1 .\dist\AVcleaner -RunTempExecution
.\packaging\create_release_zip.ps1 -SmokeTested
.\scripts\check_artifact.ps1 .\release\AVcleaner-v0.6.1-portable-win-x64.zip
.\scripts\smoke_release_zip.ps1 .\release\AVcleaner-v0.6.1-portable-win-x64.zip
Get-FileHash .\release\AVcleaner-v0.6.1-portable-win-x64.zip -Algorithm SHA256
```

`smoke_packaged.ps1` is non-mutating by default. The `-RunTempExecution` mode
copies the packaged app to `%TEMP%`, creates synthetic files under a temporary
scan root, runs scan -> plan -> validate -> execution summary -> execute ->
rollback, and deletes the temporary directories only after success. It preserves
the temp paths on failure for debugging.

`create_release_zip.ps1` produces:

```text
release\AVcleaner-v0.6.1-portable-win-x64.zip
release\AVcleaner-v0.6.1-portable-win-x64.zip.sha256
release\artifact-manifest.json
```

The release zip excludes development folders, tests, runtime databases, logs,
quarantine contents, Git metadata, and key-like secrets. The manifest records
version, commit, dirty state, Python/PyInstaller versions, included top-level
files, excluded patterns, checksum, capabilities version, and smoke status
without storing API keys or user media paths.

Normal development checks do not require PyInstaller. Packaging checks can be
added when a build exists:

```powershell
.\scripts\check.ps1 -WithPackaging
```

## Safety Defaults

- No file is renamed or quarantined during scan or plan generation.
- Execution requires a persisted `plan_id`, matching `plan_hash`, selected item ids,
  and an explicit `confirm: true` API request.
- Existing files are never overwritten.
- Quarantined files prefer `{scan_root}\.avcleaner_quarantine\{run_id}` so large
  files stay on the same volume; AppData quarantine is only a fallback.
- Subtitle, image, and NFO sidecars are not treated as junk by default and are
  not selected for rename by default.
- Selection state is stored in the server-side persisted plan. Blocking items
  cannot be selected, and sidecar rename suggestions are only selected when the
  user explicitly chooses them.
- Cloud LLM requests send filenames only by default, not full paths.
- OpenAI-compatible providers default to strict JSON Schema. Prompt JSON
  compatibility modes accept fenced/surrounded JSON or a single suggestion
  object only at the raw parsing boundary, then normalize to the canonical
  batch shape.
- LLM suggestions never execute directly, never auto-select items, and never
  replace `target_name` until the user explicitly accepts one.
- LLM output still must pass strict canonical validation and the normal
  filesystem validators before it can be stored as a valid review suggestion.
- Plan-level LLM endpoints are the supported path. Generic
  `POST /api/llm/suggest` is disabled with
  `error_code=legacy_llm_suggest_disabled`.
- All filesystem, plan, run, settings, rollback, and LLM APIs require the local
  `X-AVCleaner-Token` header injected into the GUI at startup.
- Legacy `POST /api/execute` is disabled by default and does not execute
  frontend-supplied file operations.

## API Flow

```text
POST /api/scan
POST /api/plans
GET  /api/plans/{plan_id}
POST /api/plans/{plan_id}/validate
PATCH /api/plans/{plan_id}/items/{item_id}
PATCH /api/plans/{plan_id}/selection
POST /api/plans/{plan_id}/execution-summary
GET  /api/health
GET  /api/plans/{plan_id}/export.json
GET  /api/plans/{plan_id}/export.csv
POST /api/plans/{plan_id}/llm/payload-preview
POST /api/plans/{plan_id}/llm/suggest
GET  /api/plans/{plan_id}/llm/suggestions
POST /api/plans/{plan_id}/llm/suggestions/{suggestion_id}/accept
POST /api/plans/{plan_id}/llm/suggestions/{suggestion_id}/reject
POST /api/plans/{plan_id}/execute
POST /api/rules/test
GET  /api/rules/corpus-report
GET  /api/settings/export
POST /api/settings/import
POST /api/runs/{run_id}/rollback
```

Execution accepts only:

```json
{
  "selected_item_ids": ["..."],
  "confirm": true,
  "plan_hash": "..."
}
```

`POST /api/rules/test` is token-protected and non-mutating. It accepts one
filename and returns a `RuleSuggestion` with trace plus a validation preview. It
does not scan folders, create plans, create runs, quarantine files, or execute
renames.

`GET /api/rules/corpus-report` is token-protected and non-mutating. It reads only
the repository fixtures under `tests/fixtures/filenames/` and returns structured
summary counts.

`GET /api/settings/export` and `POST /api/settings/import` handle non-secret
settings. Import supports dry-run validation, rejects invalid RuleSettings with
stable error codes, and ignores LLM API keys.

`GET /api/health` is token-protected because it returns runtime paths. It checks
database access, writable data directory, templates/static assets, keyring
availability, and runtime mode.

Manual row edits accept only `target_name`. Path separators, empty names, and
extension changes are rejected before the plan is revalidated. JSON and CSV plan
exports are token-protected, non-mutating, and contain no secrets.

LLM review endpoints are token-protected. Payload preview is non-mutating and
shows exactly what filename-level data will be sent. By default AVcleaner sends
filename, extension, rule suggestion, media code, sidecar metadata, and neighbor
filenames, but not full local paths. Generated suggestions are stored as
advisory records and validated with the same backend validators used by manual
edits. Accepting a suggestion updates the persisted plan and recomputes
`plan_hash`; stale suggestions and suggestions that would overwrite a manual
edit are rejected. Rejecting a suggestion changes only suggestion status.
Neither action executes files.

Legacy `POST /api/execute` remains disabled with `410` and
`error_code=legacy_execute_disabled`.

Legacy generic `POST /api/llm/suggest` remains token-protected but is disabled
with `410` and `error_code=legacy_llm_suggest_disabled`. Use the plan-level LLM
review endpoints instead.

## LLM Provider Compatibility

Supported modes:

- `openai_strict_json_schema`: sends OpenAI `response_format=json_schema` with
  `strict: true`; this is the default for OpenAI-compatible settings.
- `prompt_json_compat`: avoids `response_format` and instructs the provider to
  return exactly one JSON object.
- `claude_gateway_compat`: same prompt-JSON request style, with parser support
  for common gateway outputs such as Markdown fenced JSON and a single
  suggestion object.
- `ollama_format_json`: keeps Ollama's JSON format behavior.

This is a wide-input, strict-output layer. Compatibility parsing may extract or
wrap JSON, but it does not invent missing fields, repair unsafe names, change
extensions, or bypass Pydantic validation and `validators.py`.
Compatibility mode does not bypass validation.

The GUI repeats the same rule in plain language: compatibility mode does not
bypass validation, suggestions still need user acceptance, and LLM endpoints
never execute files.

## Known limitations

- AVcleaner does not scrape metadata, download covers, generate NFO files, move
  files into the final media library, or integrate with OpenAver databases.
- It does not install or manage Radarr/Sonarr.
- There is no installer yet; use the portable zip.
- Diagnostics intentionally redact secrets, raw LLM payloads, and full media
  paths. Open logs/data folder buttons are deferred in the packaged GUI because
  exposing local paths from diagnostics is not worth the risk in this beta.
- Clean Windows 10/11 manual verification may still be pending for a new release
  artifact until the checklist in `RELEASE_CHECKLIST.md` is completed.

## Rule Quality Tooling

Run the golden corpus report:

```powershell
.\.venv\Scripts\python.exe tools\rule_corpus_report.py
```

Or use:

```powershell
.\scripts\corpus.ps1
```

The report reads only `tests/fixtures/filenames/`, calls the local rule function,
prints pass/fail totals by fixture, recognized code counts, review counts, and
warning counts, then exits non-zero if any fixture expectation fails.

Trace semantics are covered by tests so rule suggestions keep meaningful steps
such as ad removal, noise removal, media-code detection, normalization, extension
preservation, and final template rendering. The v0.2 execution safety model is
unchanged: validators remain authoritative, and execution still requires
server-persisted `plan_id` plus matching `plan_hash`.

For a full local check, use:

```powershell
.\scripts\check.ps1
```

The check script runs pytest, the corpus report, `git diff --check`, and
`node --check avcleaner/static/app.js` when Node is available.

The packaging release gates and clean Windows manual checklist are listed in
`RELEASE_CHECKLIST.md`.
