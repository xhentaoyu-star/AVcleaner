$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Spec = Join-Path $Root "packaging\pyinstaller\avcleaner.spec"
$DistDir = Join-Path $Root "dist\AVcleaner"

if (-not (Test-Path $Python)) {
  Write-Error "Project venv Python not found: .venv\Scripts\python.exe"
}

Push-Location $Root
try {
  & $Python -m PyInstaller --version | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller is not installed. Run .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt"
  }

  & $Python -m PyInstaller $Spec --noconfirm --clean
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  if (-not (Test-Path $DistDir)) {
    Write-Error "Expected portable output was not created: $DistDir"
  }

  Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination (Join-Path $DistDir "README.md") -Force
  if (Test-Path (Join-Path $Root "RELEASE_CHECKLIST.md")) {
    Copy-Item -LiteralPath (Join-Path $Root "RELEASE_CHECKLIST.md") -Destination (Join-Path $DistDir "RELEASE_CHECKLIST.md") -Force
  }
  if (Test-Path (Join-Path $Root "LICENSE")) {
    Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination (Join-Path $DistDir "LICENSE") -Force
  }

  @"
AVcleaner Portable

Run AVcleaner.exe to open the desktop wrapper.
Portable mode is enabled by portable.flag next to the executable.
Runtime data is created beside the executable under:
- data
- logs
- quarantine

The app binds to 127.0.0.1 only by default.
"@ | Set-Content -LiteralPath (Join-Path $DistDir "QUICKSTART.txt") -Encoding UTF8

  New-Item -ItemType File -Path (Join-Path $DistDir "portable.flag") -Force | Out-Null

  Write-Output "Portable package created: $DistDir"
} finally {
  Pop-Location
}
