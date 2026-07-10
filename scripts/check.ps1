param(
  [switch]$WithPackaging
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$AppJs = Join-Path $Root "avcleaner\static\app.js"

if (-not (Test-Path $Python)) {
  Write-Error "Project venv Python not found: .venv\Scripts\python.exe"
}
$ExpectedVersion = (& $Python -c "from avcleaner import __version__; print(__version__)").Trim()

Push-Location $Root
try {
  & $Python -m pytest tests -q
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & $Python tools\rule_corpus_report.py
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & git diff --check
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  if ((Test-Path $AppJs) -and (Get-Command node -ErrorAction SilentlyContinue)) {
    & node --check avcleaner/static/app.js
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  }

  if ($WithPackaging) {
    $Artifact = Join-Path $Root "dist\AVcleaner"
    if (Test-Path $Artifact) {
      & (Join-Path $Root "scripts\check_artifact.ps1") $Artifact
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      & (Join-Path $Root "scripts\smoke_packaged.ps1") $Artifact -ExpectedVersion $ExpectedVersion
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
      & (Join-Path $Root "scripts\smoke_packaged.ps1") $Artifact -ExpectedVersion $ExpectedVersion -RunTempExecution
      if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } else {
      Write-Output "Packaging checks skipped: dist\AVcleaner does not exist."
    }
  }
} finally {
  Pop-Location
}
