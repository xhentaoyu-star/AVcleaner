param(
  [Parameter(Mandatory = $true)]
  [string]$AppPath,
  [string]$ExpectedVersion = "0.5.0"
)

$ErrorActionPreference = "Stop"

function Get-FreeLoopbackPort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), 0)
  $listener.Start()
  $port = $listener.LocalEndpoint.Port
  $listener.Stop()
  return $port
}

function Get-AppExecutable([string]$PathValue) {
  if (-not (Test-Path -LiteralPath $PathValue)) {
    Write-Error "Packaged app path not found: $PathValue"
  }
  $item = Get-Item -LiteralPath $PathValue
  if (-not $item.PSIsContainer) {
    return $item.FullName
  }
  $candidate = Join-Path $item.FullName "AVcleaner.exe"
  if (Test-Path -LiteralPath $candidate) {
    return $candidate
  }
  $found = Get-ChildItem -LiteralPath $item.FullName -Recurse -Filter "AVcleaner.exe" -File -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($found) {
    return $found.FullName
  }
  Write-Error "Could not find AVcleaner.exe under: $PathValue"
}

function Invoke-Json($Method, $Uri, $Headers = @{}, $Body = $null) {
  $params = @{ Method = $Method; Uri = $Uri; Headers = $Headers; UseBasicParsing = $true }
  if ($null -ne $Body) {
    $params.ContentType = "application/json"
    $params.Body = ($Body | ConvertTo-Json -Depth 20)
  }
  return Invoke-RestMethod @params
}

$sourceItem = Get-Item -LiteralPath $AppPath
$sourceRoot = if ($sourceItem.PSIsContainer) { $sourceItem.FullName } else { $sourceItem.DirectoryName }
$tempAppRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("avcleaner-packaged-app-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempAppRoot | Out-Null
Get-ChildItem -LiteralPath $sourceRoot -Force | Copy-Item -Destination $tempAppRoot -Recurse -Force
$exe = Get-AppExecutable $tempAppRoot
$port = Get-FreeLoopbackPort
$base = "http://127.0.0.1:$port"
$process = $null
$tempScan = $null

try {
  $process = Start-Process -FilePath $exe -ArgumentList @("--no-window", "--host", "127.0.0.1", "--port", "$port", "--strict-port", "--portable") -PassThru -WindowStyle Hidden

  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
      $capabilities = Invoke-Json GET "$base/api/capabilities"
      $ready = $true
      break
    } catch {
      if ($process.HasExited) {
        Write-Error "AVcleaner process exited before readiness check completed."
      }
    }
  }
  if (-not $ready) {
    Write-Error "Timed out waiting for AVcleaner packaged app."
  }

  if ($capabilities.version -ne $ExpectedVersion) {
    Write-Error "Unexpected version. Expected $ExpectedVersion, got $($capabilities.version)."
  }
  if (-not $capabilities.capabilities.packaging_ready) { Write-Error "packaging_ready capability missing." }
  if (-not $capabilities.capabilities.portable_mode) { Write-Error "portable_mode capability missing." }
  if (-not $capabilities.capabilities.health_check) { Write-Error "health_check capability missing." }

  $frontPage = Invoke-WebRequest -Uri $base -UseBasicParsing
  $tokenMatch = [regex]::Match($frontPage.Content, 'name="avcleaner-token"\s+content="([^"]+)"')
  if (-not $tokenMatch.Success) {
    Write-Error "Could not find API token in packaged frontend."
  }
  $headers = @{ "X-AVCleaner-Token" = $tokenMatch.Groups[1].Value }

  $health = Invoke-Json GET "$base/api/health" $headers
  if (-not $health.ok) { Write-Error "Health endpoint returned ok=false." }
  if ($health.mode -ne "portable") { Write-Error "Expected portable mode, got $($health.mode)." }

  try {
    Invoke-Json POST "$base/api/execute" $headers @{ confirm = $true; items = @() } | Out-Null
    Write-Error "Legacy execute unexpectedly succeeded."
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 410) { throw }
  }
  try {
    Invoke-Json POST "$base/api/llm/suggest" $headers @{ items = @() } | Out-Null
    Write-Error "Legacy LLM suggest unexpectedly succeeded."
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 410) { throw }
  }

  $tempScan = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) ("avcleaner-smoke-" + [guid]::NewGuid().ToString("N")))
  Set-Content -LiteralPath (Join-Path $tempScan.FullName "hhd800.com@ABP-123.mp4") -Value "video"

  $scan = Invoke-Json POST "$base/api/scan" $headers @{ root_path = $tempScan.FullName; recursive = $true }
  $plan = Invoke-Json POST "$base/api/plans" $headers @{ scan_id = $scan.scan_id }
  $validated = Invoke-Json POST "$base/api/plans/$($plan.plan_id)/validate" $headers
  if (-not $validated.plan_hash) { Write-Error "Validate did not return plan_hash." }

  Write-Output "Packaged smoke passed: $exe"
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
  if ($tempScan -and (Test-Path -LiteralPath $tempScan.FullName)) {
    Remove-Item -LiteralPath $tempScan.FullName -Recurse -Force
  }
  if (Test-Path -LiteralPath $tempAppRoot) {
    Remove-Item -LiteralPath $tempAppRoot -Recurse -Force
  }
}
