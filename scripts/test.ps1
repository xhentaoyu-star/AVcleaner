$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "Project venv Python not found: .venv\Scripts\python.exe"
}

& $Python -m pytest tests -q
exit $LASTEXITCODE
