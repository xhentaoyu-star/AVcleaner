param(
  [Parameter(Mandatory = $true)]
  [string]$ZipPath,
  [string]$ExpectedVersion = "0.8.1"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SmokePackaged = Join-Path $PSScriptRoot "smoke_packaged.ps1"

function Invoke-PackagedSmoke([string]$PackageRoot, [string]$Version, [switch]$RunTempExecution) {
  if ($RunTempExecution) {
    & $SmokePackaged $PackageRoot -ExpectedVersion $Version -RunTempExecution
  } else {
    & $SmokePackaged $PackageRoot -ExpectedVersion $Version
  }
  if (-not $?) {
    Write-Error "Packaged smoke failed."
  }
}

if (-not (Test-Path -LiteralPath $ZipPath)) {
  Write-Error "Release zip not found: $ZipPath"
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("avcleaner-release-zip-smoke-" + [System.Guid]::NewGuid().ToString("N"))
$success = $false

try {
  New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
  Expand-Archive -LiteralPath $ZipPath -DestinationPath $tempRoot -Force

  $packageRoot = Join-Path $tempRoot "AVcleaner"
  if (-not (Test-Path -LiteralPath (Join-Path $packageRoot "AVcleaner.exe"))) {
    $exe = Get-ChildItem -LiteralPath $tempRoot -Recurse -Filter "AVcleaner.exe" -File -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if (-not $exe) {
      Write-Error "AVcleaner.exe not found after expanding release zip."
    }
    $packageRoot = Split-Path -Parent $exe.FullName
  }

  Invoke-PackagedSmoke $packageRoot $ExpectedVersion
  Invoke-PackagedSmoke $packageRoot $ExpectedVersion -RunTempExecution

  $success = $true
  Write-Output "Release zip smoke passed: $ZipPath"
} finally {
  if ($success) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  } else {
    Write-Warning "Preserving temp directory for inspection: $tempRoot"
  }
}
