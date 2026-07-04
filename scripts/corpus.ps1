$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "Project venv Python not found: .venv\Scripts\python.exe"
}

& $Python tools\rule_corpus_report.py
exit $LASTEXITCODE
