# AVcleaner Release Checklist

Use this checklist before publishing a Windows build.

- Run `.\scripts\check.ps1`.
- Run `.\.venv\Scripts\python.exe tools\rule_corpus_report.py`.
- Build the portable package with `.\packaging\build_portable.ps1`.
- Inspect the artifact with `.\scripts\check_artifact.ps1 .\dist\AVcleaner`.
- Smoke-test the packaged app with `.\scripts\smoke_packaged.ps1 .\dist\AVcleaner`.
- Run temp-only execute and rollback smoke with
  `.\scripts\smoke_packaged.ps1 .\dist\AVcleaner -RunTempExecution`.
- Create the release zip with `.\packaging\create_release_zip.ps1 -SmokeTested`.
- Verify the zip with
  `.\scripts\check_artifact.ps1 .\release\AVcleaner-v0.7.4-portable-win-x64.zip`.
- Smoke-test the final zip directly with
  `.\scripts\smoke_release_zip.ps1 .\release\AVcleaner-v0.7.4-portable-win-x64.zip`.
- Verify `release\AVcleaner-v0.7.4-portable-win-x64.zip.sha256`.
- Verify SHA256 with
  `Get-FileHash .\release\AVcleaner-v0.7.4-portable-win-x64.zip -Algorithm SHA256`.
- Verify `release\artifact-manifest.json`.
- Test on a clean Windows 10/11 x64 VM before public release.
- v0.7.4 clean Windows manual checklist:
  - Windows 10 x64 clean VM.
  - Windows 11 x64 clean VM.
  - Run portable package from Downloads.
  - Run portable package from a path with spaces.
  - Run portable package from a non-ASCII path.
  - Run portable package from an external drive if available.
  - Verify AppData mode.
  - Verify portable mode using `portable.flag` or `--portable`.
  - Verify `GET /api/health` with token.
  - Verify scan -> plan -> validate.
  - Verify temp execute -> rollback.
  - Verify legacy endpoints are disabled.
  - Verify LLM review disabled/not configured behaves gracefully.
  - Verify no full paths are sent to LLM by default.
  - Verify uninstall/delete of a portable folder leaves no unexpected files
    except documented AppData data if AppData mode was used.
- Verify AppData mode stores data under `%LOCALAPPDATA%\AVcleaner`.
- Verify portable mode stores data beside the executable under `data`, `logs`,
  and `quarantine`.
- Verify package contents do not include `.venv`, tests, Git metadata, user DBs,
  logs, quarantine contents, or API keys.
- Verify `GET /api/health` returns `ok=true` with token.
- Verify `POST /api/execute` returns `410` and
  `error_code=legacy_execute_disabled`.
- Verify `POST /api/llm/suggest` returns `410` and
  `error_code=legacy_llm_suggest_disabled`.
- Verify LLM payload preview does not include full local paths by default.
- Verify rollback and same-root quarantine behavior on temporary files only.
- Verify README version matches `/api/capabilities`.
- Create a git tag only after all checks pass.
- Attach artifacts only after artifact sanity and smoke tests pass.
