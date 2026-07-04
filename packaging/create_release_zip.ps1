param(
  [string]$Version = "0.5.1",
  [string]$DistPath = "",
  [string]$ReleaseDir = "",
  [switch]$Build,
  [switch]$SmokeTested
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $DistPath) { $DistPath = Join-Path $Root "dist\AVcleaner" }
if (-not $ReleaseDir) { $ReleaseDir = Join-Path $Root "release" }
$BuildScript = Join-Path $Root "packaging\build_portable.ps1"
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if ($Build) {
  & $BuildScript
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path -LiteralPath $DistPath)) {
  Write-Error "Portable dist path not found: $DistPath. Run .\packaging\build_portable.ps1 or pass -Build."
}

$DistItem = Get-Item -LiteralPath $DistPath
if (-not $DistItem.PSIsContainer) {
  Write-Error "DistPath must be a portable directory, not a file: $DistPath"
}

$ZipName = "AVcleaner-v$Version-portable-win-x64.zip"
$ZipPath = Join-Path $ReleaseDir $ZipName
$ShaPath = "$ZipPath.sha256"
$ManifestPath = Join-Path $ReleaseDir "artifact-manifest.json"
$StagingDir = Join-Path $ReleaseDir ".staging"
$PackageDir = Join-Path $StagingDir "AVcleaner"

$ExcludedPatterns = @(
  ".venv",
  "build",
  "tests",
  ".pytest_cache",
  "__pycache__",
  ".git",
  "logs",
  "quarantine",
  "*.db",
  "*.db-shm",
  "*.db-wal",
  "*.sqlite",
  "*.sqlite3",
  "*.log"
)

function Test-ExcludedPath([string]$RelativePath, [string]$Name) {
  $parts = $RelativePath -split "[\\/]"
  foreach ($part in $parts) {
    if ($part -in @(".venv", "build", "tests", ".pytest_cache", "__pycache__", ".git", "logs", "quarantine")) {
      return $true
    }
  }
  foreach ($pattern in @("*.db", "*.db-shm", "*.db-wal", "*.sqlite", "*.sqlite3", "*.log")) {
    if ($Name -like $pattern) {
      return $true
    }
  }
  return $false
}

function Invoke-OptionalCommand([scriptblock]$Command) {
  try {
    $value = & $Command
    if ($null -eq $value) { return "" }
    return (($value | Out-String).Trim())
  } catch {
    return ""
  }
}

function Set-Utf8NoBom([string]$Path, [string]$Content) {
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
if (Test-Path -LiteralPath $StagingDir) {
  Remove-Item -LiteralPath $StagingDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null

$SourceRoot = $DistItem.FullName.TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
$files = Get-ChildItem -LiteralPath $SourceRoot -Recurse -Force -File -ErrorAction SilentlyContinue
foreach ($file in $files) {
  $relative = $file.FullName.Substring($SourceRoot.Length).TrimStart([char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar))
  if (Test-ExcludedPath $relative $file.Name) {
    continue
  }
  $destination = Join-Path $PackageDir $relative
  $destinationParent = Split-Path -Parent $destination
  New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
  Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $PackageDir "AVcleaner.exe"))) {
  Write-Error "Release package is missing AVcleaner.exe."
}
if (-not ((Test-Path -LiteralPath (Join-Path $PackageDir "README.md")) -or (Test-Path -LiteralPath (Join-Path $PackageDir "QUICKSTART.txt")))) {
  Write-Error "Release package must include README.md or QUICKSTART.txt."
}

$GitCommit = Invoke-OptionalCommand { git -C $Root rev-parse HEAD }
$GitStatus = Invoke-OptionalCommand { git -C $Root status --porcelain }
$GitDirty = -not [string]::IsNullOrWhiteSpace($GitStatus)
$PythonVersion = if (Test-Path -LiteralPath $Python) { Invoke-OptionalCommand { & $Python --version } } else { "" }
$PyInstallerVersion = if (Test-Path -LiteralPath $Python) { Invoke-OptionalCommand { & $Python -m PyInstaller --version } } else { "" }
$CapabilitiesVersion = if (Test-Path -LiteralPath $Python) { Invoke-OptionalCommand { & $Python -c "from avcleaner import __version__; print(__version__)" } } else { $Version }
$BuildTimeUtc = [DateTime]::UtcNow.ToString("o")
$IncludedTopLevelFiles = @(Get-ChildItem -LiteralPath $PackageDir -Force | Sort-Object Name | ForEach-Object { $_.Name })

$ManifestBase = [ordered]@{
  app_name = "AVcleaner"
  version = $Version
  build_time_utc = $BuildTimeUtc
  git_commit = $GitCommit
  git_dirty = $GitDirty
  python_version_used_for_build = $PythonVersion
  pyinstaller_version = $PyInstallerVersion
  artifact_name = $ZipName
  artifact_sha256 = ""
  included_top_level_files = $IncludedTopLevelFiles
  excluded_patterns = $ExcludedPatterns
  capabilities_version = $CapabilitiesVersion
  smoke_tested = [bool]$SmokeTested
}

Set-Utf8NoBom (Join-Path $PackageDir "artifact-manifest.json") ($ManifestBase | ConvertTo-Json -Depth 10)

if (Test-Path -LiteralPath $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path $PackageDir -DestinationPath $ZipPath -Force

$Hash = (Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $ZipName" | Set-Content -LiteralPath $ShaPath -Encoding ASCII

$ExternalManifest = [ordered]@{}
foreach ($key in $ManifestBase.Keys) {
  $ExternalManifest[$key] = $ManifestBase[$key]
}
$ExternalManifest["artifact_sha256"] = $Hash
Set-Utf8NoBom $ManifestPath ($ExternalManifest | ConvertTo-Json -Depth 10)

Remove-Item -LiteralPath $StagingDir -Recurse -Force

Write-Output "Release zip created: $ZipPath"
Write-Output "SHA256: $Hash"
Write-Output "Manifest: $ManifestPath"
