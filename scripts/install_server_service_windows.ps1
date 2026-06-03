$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir '..')).Path
$wrapperPath = Join-Path $scriptDir 'run_battery_web_service.sh'
$taskName = 'BatteryHealthAnalyzerWebService'
$portValue = if ($env:PORT) { $env:PORT } else { '8000' }

param(
  [string]$Port = ''
)

if ($Port -ne '') {
  $portValue = $Port
}

function Test-Administrator {
  $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
  return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Administrator)) {
  throw 'This installer must be executed as Administrator.'
}

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
  throw 'Node.js was not found in PATH.'
}
$nodeExe = $nodeCmd.Source

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npmCmd) {
  throw 'npm was not found in PATH.'
}
$npmExe = $npmCmd.Source

if (-not (Test-Path (Join-Path $projectDir 'node_modules'))) {
  Write-Host 'Installing Node.js dependencies...'
  Push-Location $projectDir
  try {
    & $npmExe install | Out-Host
  }
  finally {
    Pop-Location
  }
}

$actionArgument = "/c set PORT=$portValue && cd /d `"$projectDir`" && `"$npmExe`" start"
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument $actionArgument -WorkingDirectory $projectDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Battery Health Analyzer web service (Node.js)'

try {
  Start-ScheduledTask -TaskName $taskName
  Write-Host "Started scheduled task now: $taskName"
} catch {
  Write-Warning "Task installed but could not be started immediately: $($_.Exception.Message)"
}

Write-Host "Installed optional web service task: $taskName"
Write-Host "Port: $portValue"
Write-Host "Status: Get-ScheduledTask -TaskName $taskName"
