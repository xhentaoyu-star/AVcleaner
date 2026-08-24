param(
  [Parameter(Mandatory = $true)]
  [string]$ArtifactPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ArtifactPath)) {
  Write-Error "Artifact path not found: $ArtifactPath"
}

function Get-Sha256Hex([string]$Path) {
  $stream = [System.IO.File]::OpenRead($Path)
  $sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    return (-join ($sha256.ComputeHash($stream) | ForEach-Object { $_.ToString("x2") }))
  } finally {
    $sha256.Dispose()
    $stream.Dispose()
  }
}

function Get-PackageRoot([string]$SearchRoot) {
  $directExe = Join-Path $SearchRoot "AVcleaner.exe"
  if (Test-Path -LiteralPath $directExe) {
    return $SearchRoot
  }
  $exe = Get-ChildItem -LiteralPath $SearchRoot -Recurse -Force -File -Filter "AVcleaner.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $exe) {
    Write-Error "Expected executable AVcleaner.exe is missing from artifact."
  }
  return $exe.DirectoryName
}

function Test-ChecksumFile([string]$ZipPath) {
  $shaPath = "$ZipPath.sha256"
  if (-not (Test-Path -LiteralPath $shaPath)) {
    return
  }
  $content = Get-Content -LiteralPath $shaPath -Raw
  $match = [regex]::Match($content, "(?i)[a-f0-9]{64}")
  if (-not $match.Success) {
    Write-Error "Checksum file does not contain a SHA256 hash: $shaPath"
  }
  $expected = $match.Value.ToLowerInvariant()
  $actual = Get-Sha256Hex $ZipPath
  if ($expected -ne $actual) {
    Write-Error "Checksum mismatch for zip artifact. Expected $expected, got $actual."
  }
}

$RootItem = Get-Item -LiteralPath $ArtifactPath
$TempExtract = $null
$InspectRoot = $null

try {
  if ((-not $RootItem.PSIsContainer) -and $RootItem.Extension -ieq ".zip") {
    Test-ChecksumFile $RootItem.FullName
    $TempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("avcleaner-artifact-check-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $TempExtract | Out-Null
    Expand-Archive -LiteralPath $RootItem.FullName -DestinationPath $TempExtract -Force
    $InspectRoot = $TempExtract
  } elseif ($RootItem.PSIsContainer) {
    $InspectRoot = $RootItem.FullName
  } else {
    Write-Error "Artifact must be a portable directory or a release zip: $ArtifactPath"
  }

  $PackageRoot = Get-PackageRoot $InspectRoot

  $ForbiddenDirs = @(".venv", "__pycache__", ".pytest_cache", ".git", "tests", "build")
  $ForbiddenRuntimeDirs = @("logs", "quarantine")
  $ForbiddenFiles = @("*.db", "*.db-shm", "*.db-wal", "*.sqlite", "*.sqlite3", "*.log")

  foreach ($dirName in $ForbiddenDirs) {
    $hit = Get-ChildItem -LiteralPath $InspectRoot -Recurse -Force -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -eq $dirName } |
      Select-Object -First 1
    if ($hit) {
      Write-Error "Forbidden directory included in artifact: $($hit.FullName)"
    }
  }

  foreach ($dirName in $ForbiddenRuntimeDirs) {
    $hit = Get-ChildItem -LiteralPath $InspectRoot -Recurse -Force -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -eq $dirName } |
      Select-Object -First 1
    if ($hit) {
      Write-Error "Forbidden runtime directory included in artifact: $($hit.FullName)"
    }
  }

  foreach ($pattern in $ForbiddenFiles) {
    $hit = Get-ChildItem -LiteralPath $InspectRoot -Recurse -Force -File -Filter $pattern -ErrorAction SilentlyContinue |
      Select-Object -First 1
    if ($hit) {
      Write-Error "Forbidden runtime file included in artifact: $($hit.FullName)"
    }
  }

  $TemplateCandidates = @(
    (Join-Path $PackageRoot "avcleaner\templates\index.html"),
    (Join-Path $PackageRoot "_internal\avcleaner\templates\index.html")
  )
  $StaticCandidates = @(
    (Join-Path $PackageRoot "avcleaner\static"),
    (Join-Path $PackageRoot "_internal\avcleaner\static")
  )
  if (-not ($TemplateCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)) {
    Write-Error "Template assets are missing from artifact."
  }
  if (-not ($StaticCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)) {
    Write-Error "Static assets are missing from artifact."
  }

  if (-not ((Test-Path -LiteralPath (Join-Path $PackageRoot "README.md")) -or (Test-Path -LiteralPath (Join-Path $PackageRoot "QUICKSTART.txt")))) {
    Write-Error "Artifact must include README.md or QUICKSTART.txt."
  }

  if ($RootItem.Extension -ieq ".zip" -and -not (Test-Path -LiteralPath (Join-Path $PackageRoot "artifact-manifest.json"))) {
    Write-Error "Release zip must include artifact-manifest.json."
  }

  $SecretPattern = "(?i)(sk-[a-z0-9_-]{20,}|bearer\s+[a-z0-9._-]{20,}|api[_-]?key\s*[:=]\s*['""]?[a-z0-9_-]{16,})"
  $TextExtensions = @(".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".html", ".js", ".css", ".ps1")
  $textFiles = Get-ChildItem -LiteralPath $InspectRoot -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $TextExtensions -contains $_.Extension.ToLowerInvariant() }
  foreach ($file in $textFiles) {
    $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -match $SecretPattern) {
      Write-Error "Possible API key-like secret found in artifact text file: $($file.FullName)"
    }
  }

  Write-Output "Artifact sanity check passed: $ArtifactPath"
} finally {
  if ($TempExtract -and (Test-Path -LiteralPath $TempExtract)) {
    Remove-Item -LiteralPath $TempExtract -Recurse -Force
  }
}
