# AVcleaner Release Checklist

Use this checklist before publishing a Windows build.

- Run `.\scripts\check.ps1`.
- Run `.\.venv\Scripts\python.exe tools\rule_corpus_report.py`.
- Build the portable package with `.\packaging\build_portable.ps1`.
- Inspect the artifact with `.\scripts\check_artifact.ps1 .\dist\AVcleaner`.
- Smoke-test the packaged app with `.\scripts\smoke_packaged.ps1 .\dist\AVcleaner`.
- Test on a clean Windows 10/11 x64 VM before public release.
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
