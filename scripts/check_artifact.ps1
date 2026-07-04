param(
  [Parameter(Mandatory = $true)]
  [string]$ArtifactPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ArtifactPath)) {
  Write-Error "Artifact path not found: $ArtifactPath"
}

$RootItem = Get-Item -LiteralPath $ArtifactPath
$Root = if ($RootItem.PSIsContainer) { $RootItem.FullName } else { $RootItem.DirectoryName }

$ForbiddenDirs = @(".venv", "__pycache__", ".pytest_cache", ".git", "tests")
$ForbiddenFiles = @("*.db", "*.db-shm", "*.db-wal", "*.log")
$ForbiddenRuntimeDirs = @("logs", "quarantine")

foreach ($dirName in $ForbiddenDirs) {
  $hit = Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq $dirName } |
    Select-Object -First 1
  if ($hit) {
    Write-Error "Forbidden directory included in artifact: $($hit.FullName)"
  }
}

foreach ($dirName in $ForbiddenRuntimeDirs) {
  $runtimeDir = Join-Path $Root $dirName
  if ((Test-Path -LiteralPath $runtimeDir) -and (Get-ChildItem -LiteralPath $runtimeDir -Force -ErrorAction SilentlyContinue)) {
    Write-Error "Runtime directory contains files and must not be packaged: $runtimeDir"
  }
}

foreach ($pattern in $ForbiddenFiles) {
  $hit = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -Filter $pattern -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($hit) {
    Write-Error "Forbidden runtime file included in artifact: $($hit.FullName)"
  }
}

$TemplateCandidates = @(
  (Join-Path $Root "avcleaner\templates\index.html"),
  (Join-Path $Root "_internal\avcleaner\templates\index.html")
)
$StaticCandidates = @(
  (Join-Path $Root "avcleaner\static"),
  (Join-Path $Root "_internal\avcleaner\static")
)
if (-not ($TemplateCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)) {
  Write-Error "Template assets are missing from artifact."
}
if (-not ($StaticCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)) {
  Write-Error "Static assets are missing from artifact."
}

if (-not ((Test-Path -LiteralPath (Join-Path $Root "README.md")) -or (Test-Path -LiteralPath (Join-Path $Root "QUICKSTART.txt")))) {
  Write-Error "Artifact must include README.md or QUICKSTART.txt."
}

$SecretPattern = "(?i)(sk-[a-z0-9_-]{20,}|bearer\s+[a-z0-9._-]{20,}|api[_-]?key\s*[:=]\s*['""]?[a-z0-9_-]{16,})"
$TextExtensions = @(".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".html", ".js", ".css", ".ps1")
$textFiles = Get-ChildItem -LiteralPath $Root -Recurse -Force -File -ErrorAction SilentlyContinue |
  Where-Object { $TextExtensions -contains $_.Extension.ToLowerInvariant() }
foreach ($file in $textFiles) {
  $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
  if ($content -match $SecretPattern) {
    Write-Error "Possible API key-like secret found in artifact text file: $($file.FullName)"
  }
}

Write-Output "Artifact sanity check passed: $Root"
