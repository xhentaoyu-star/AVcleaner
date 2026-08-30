param(
  [Parameter(Mandatory = $true)]
  [string]$AppPath,
  [string]$ExpectedVersion = "0.8.4",
  [switch]$RunTempExecution
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

function Remove-DirectoryWithRetry(
  [Parameter(Mandatory = $true)]
  [string]$Path,
  [int]$MaxAttempts = 10,
  [int]$DelayMilliseconds = 300
) {
  if (-not (Test-Path -LiteralPath $Path)) {
    return
  }

  $lastError = $null
  for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    try {
      Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
      return
    } catch {
      $lastError = $_
      if ($attempt -lt $MaxAttempts) {
        Start-Sleep -Milliseconds $DelayMilliseconds
      }
    }
  }

  throw "Could not remove smoke-test directory after $MaxAttempts attempts: $Path. $($lastError.Exception.Message)"
}

function Invoke-Json($Method, $Uri, $Headers = @{}, $Body = $null) {
  $params = @{ Method = $Method; Uri = $Uri; Headers = $Headers; UseBasicParsing = $true }
  if ($null -ne $Body) {
    $params.ContentType = "application/json"
    $params.Body = ($Body | ConvertTo-Json -Depth 20)
  }
  return Invoke-RestMethod @params
}

function Assert-EndpointStatus($Method, $Uri, $Headers, $Body, [int]$ExpectedStatus, [string]$ExpectedErrorCode) {
  try {
    Invoke-Json $Method $Uri $Headers $Body | Out-Null
    Write-Error "Endpoint unexpectedly succeeded: $Uri"
  } catch {
    $response = $_.Exception.Response
    if (-not $response) { throw }
    $actualStatus = [int]$response.StatusCode
    if ($actualStatus -ne $ExpectedStatus) {
      throw
    }
    $message = $_.ErrorDetails.Message
    if ($ExpectedErrorCode -and ($message -notmatch [regex]::Escape($ExpectedErrorCode))) {
      Write-Error "Expected error_code=$ExpectedErrorCode from $Uri, got: $message"
    }
  }
}

function Test-PathUnder([string]$Root, [string]$PathValue) {
  $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $pathFull = [System.IO.Path]::GetFullPath($PathValue)
  return $pathFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $pathFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-ExecutionOperationPaths($Operations, [string]$ScanRoot, [string]$AppRoot) {
  $quarantineRoot = Join-Path $AppRoot "quarantine"
  foreach ($operation in @($Operations)) {
    if ($operation.source_path -and -not (Test-PathUnder $ScanRoot $operation.source_path)) {
      Write-Error "Execution source path escaped temp scan root: $($operation.source_path)"
    }
    $action = [string]$operation.action
    if ($action -eq "quarantine") {
      if ($operation.target_path -and (Test-PathUnder $ScanRoot $operation.target_path)) {
        Write-Error "Quarantine target should not be under temp scan root: $($operation.target_path)"
      }
      if ($operation.target_path -and -not (Test-PathUnder $quarantineRoot $operation.target_path)) {
        Write-Error "Quarantine target escaped packaged quarantine root: $($operation.target_path)"
      }
    } elseif ($operation.target_path -and -not (Test-PathUnder $ScanRoot $operation.target_path)) {
      Write-Error "Rename target path escaped temp scan root: $($operation.target_path)"
    }
  }
}

function Assert-RollbackOperationPaths($Operations, [string]$ScanRoot, [string]$AppRoot) {
  $quarantineRoot = Join-Path $AppRoot "quarantine"
  foreach ($operation in @($Operations)) {
    $action = [string]$operation.action
    if ($action -eq "quarantine") {
      if ($operation.source_path -and -not (Test-PathUnder $quarantineRoot $operation.source_path)) {
        Write-Error "Rollback quarantine source escaped packaged quarantine root: $($operation.source_path)"
      }
    } elseif ($operation.source_path -and -not (Test-PathUnder $ScanRoot $operation.source_path)) {
      Write-Error "Rollback rename source escaped temp scan root: $($operation.source_path)"
    }
    if ($operation.target_path -and -not (Test-PathUnder $ScanRoot $operation.target_path)) {
      Write-Error "Rollback target path escaped temp scan root: $($operation.target_path)"
    }
  }
}

function Add-SmokeFiles([string]$ScanRoot, [bool]$ForExecution) {
  if ($ForExecution) {
    Set-Content -LiteralPath (Join-Path $ScanRoot "[ads.example.com] ABP123.mp4") -Value "video"
    Set-Content -LiteralPath (Join-Path $ScanRoot "junk.url") -Value "[InternetShortcut]"
    Set-Content -LiteralPath (Join-Path $ScanRoot "ABP-123.zh.srt") -Value "subtitle"
  } else {
    Set-Content -LiteralPath (Join-Path $ScanRoot "hhd800.com@ABP-123.mp4") -Value "video"
  }
}

function Invoke-TempExecutionSmoke($Base, $Headers, $Plan, [string]$ScanRoot, [string]$AppRoot) {
  $validated = Invoke-Json POST "$Base/api/plans/$($Plan.plan_id)/validate" $Headers
  if (-not $validated.plan_hash) { Write-Error "Validate did not return plan_hash." }

  $sidecar = @($validated.items | Where-Object { $_.sidecar_type -eq "subtitle" } | Select-Object -First 1)
  if (-not $sidecar) { Write-Error "Expected subtitle sidecar in temp execution plan." }
  if ($sidecar.selected -or $sidecar.checked) { Write-Error "Sidecar was selected by default." }

  $selection = Invoke-Json PATCH "$Base/api/plans/$($Plan.plan_id)/selection" $Headers @{
    mode = "select_safe"
    selected_item_ids = @()
  }
  $selectedIds = @($selection.selected_item_ids)
  if ($selectedIds.Count -lt 2) { Write-Error "Expected video rename and junk quarantine to be selected." }
  if ($selectedIds -contains $sidecar.id) { Write-Error "Sidecar was selected by select_safe." }

  $summary = Invoke-Json POST "$Base/api/plans/$($Plan.plan_id)/execution-summary" $Headers @{
    selected_item_ids = $selectedIds
    plan_hash = $selection.plan_hash
  }
  if (-not $summary.ok_to_execute) { Write-Error "Execution summary rejected temp smoke selection." }
  if ($summary.sidecar_count -ne 0) { Write-Error "Execution summary included sidecar execution unexpectedly." }

  $originalVideo = Join-Path $ScanRoot "[ads.example.com] ABP123.mp4"
  $renamedVideo = Join-Path $ScanRoot "ABP-123.mp4"
  $junk = Join-Path $ScanRoot "junk.url"
  $sidecarPath = Join-Path $ScanRoot "ABP-123.zh.srt"

  $execution = Invoke-Json POST "$Base/api/plans/$($Plan.plan_id)/execute" $Headers @{
    selected_item_ids = $selectedIds
    confirm = $true
    plan_hash = $selection.plan_hash
  }
  if (-not $execution.run_id) { Write-Error "Execute did not return run_id." }
  Assert-ExecutionOperationPaths $execution.operations $ScanRoot $AppRoot

  if (Test-Path -LiteralPath $originalVideo) { Write-Error "Original video still exists after rename execution." }
  if (-not (Test-Path -LiteralPath $renamedVideo)) { Write-Error "Renamed video missing after execution." }
  if (Test-Path -LiteralPath $junk) { Write-Error "Junk file still exists after quarantine execution." }
  if (-not (Test-Path -LiteralPath $sidecarPath)) { Write-Error "Sidecar should remain untouched during execution." }

  $rollback = Invoke-Json POST "$Base/api/runs/$($execution.run_id)/rollback" $Headers
  if (-not $rollback.run_id) { Write-Error "Rollback did not return rollback run_id." }
  Assert-RollbackOperationPaths $rollback.operations $ScanRoot $AppRoot

  if (-not (Test-Path -LiteralPath $originalVideo)) { Write-Error "Original video was not restored after rollback." }
  if (Test-Path -LiteralPath $renamedVideo) { Write-Error "Renamed video still exists after rollback." }
  if (-not (Test-Path -LiteralPath $junk)) { Write-Error "Junk file was not restored after rollback." }
  if (-not (Test-Path -LiteralPath $sidecarPath)) { Write-Error "Sidecar missing after rollback." }
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
$completed = $false

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

  Assert-EndpointStatus POST "$base/api/execute" $headers @{ confirm = $true; items = @() } 410 "legacy_execute_disabled"
  Assert-EndpointStatus POST "$base/api/llm/suggest" $headers @{ items = @() } 410 "legacy_llm_suggest_disabled"

  $tempScan = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) ("avcleaner-smoke-" + [guid]::NewGuid().ToString("N")))
  Add-SmokeFiles $tempScan.FullName $RunTempExecution.IsPresent

  $scan = Invoke-Json POST "$base/api/scan" $headers @{ root_path = $tempScan.FullName; recursive = $true }
  $plan = Invoke-Json POST "$base/api/plans" $headers @{ scan_id = $scan.scan_id }
  $validated = Invoke-Json POST "$base/api/plans/$($plan.plan_id)/validate" $headers
  if (-not $validated.plan_hash) { Write-Error "Validate did not return plan_hash." }

  if ($RunTempExecution) {
    Invoke-TempExecutionSmoke $base $headers $plan $tempScan.FullName $tempAppRoot
  }

  $completed = $true
  Write-Output "Packaged smoke passed: $exe"
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
  if ($process) {
    Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
  }
  if ($completed) {
    if ($tempScan -and (Test-Path -LiteralPath $tempScan.FullName)) {
      Remove-DirectoryWithRetry $tempScan.FullName
    }
    if (Test-Path -LiteralPath $tempAppRoot) {
      Remove-DirectoryWithRetry $tempAppRoot
    }
  } else {
    if ($tempAppRoot -and (Test-Path -LiteralPath $tempAppRoot)) {
      Write-Warning "Preserving packaged smoke temp app for debugging: $tempAppRoot"
    }
    if ($tempScan -and (Test-Path -LiteralPath $tempScan.FullName)) {
      Write-Warning "Preserving packaged smoke scan root for debugging: $($tempScan.FullName)"
    }
  }
}
