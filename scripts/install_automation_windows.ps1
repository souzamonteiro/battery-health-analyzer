$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir '..')).Path
$historyFile = Join-Path $projectDir 'battery_history.csv'
$loggerScript = Join-Path $projectDir 'battery_logger.py'
$analyzerScript = Join-Path $projectDir 'battery_health_analyzer.py'
$loggerWrapper = Join-Path $scriptDir 'run_battery_logger.cmd'
$analyzerWrapper = Join-Path $scriptDir 'open_battery_health_analyzer.cmd'
$taskName = 'BatteryHealthAnalyzerLogger'


function Test-Administrator {
	$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
	$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
	return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}


$loggerPythonCandidates = @('py', 'python')
$loggerPythonExe = $null
foreach ($candidate in $loggerPythonCandidates) {
	$cmd = Get-Command $candidate -ErrorAction SilentlyContinue
	if ($cmd) {
		$loggerPythonExe = $cmd.Source
		break
	}
}

if (-not $loggerPythonExe) {
	throw 'Python was not found in PATH.'
}

$guiPythonCandidates = @('pythonw', 'pyw', 'py', 'python')
$guiPythonExe = $null
foreach ($candidate in $guiPythonCandidates) {
	$cmd = Get-Command $candidate -ErrorAction SilentlyContinue
	if ($cmd) {
		$guiPythonExe = $cmd.Source
		break
	}
}

if (-not $guiPythonExe) {
	$guiPythonExe = $loggerPythonExe
}

if (-not (Test-Path $loggerWrapper)) {
	throw "Missing wrapper: $loggerWrapper"
}

if (-not (Test-Path $analyzerWrapper)) {
	throw "Missing wrapper: $analyzerWrapper"
}

$isElevated = Test-Administrator

$desktopPath = [Environment]::GetFolderPath('Desktop')
if (-not [string]::IsNullOrWhiteSpace($desktopPath)) {
	$wsh = New-Object -ComObject WScript.Shell
	$shortcutPath = Join-Path $desktopPath 'Battery Health Analyzer.lnk'
	$shortcut = $wsh.CreateShortcut($shortcutPath)
	$shortcut.TargetPath = $guiPythonExe
	$shortcut.Arguments = "`"$analyzerScript`" `"$historyFile`""
	$shortcut.WorkingDirectory = $projectDir
	$shortcut.Description = 'Open Battery Health Analyzer with the default history file'
	$shortcut.IconLocation = "$guiPythonExe,0"
	$shortcut.Save()
}

$action = New-ScheduledTaskAction -Execute $loggerPythonExe -Argument "`"$loggerScript`" --loop --interval-seconds 60 --output `"$historyFile`"" -WorkingDirectory $projectDir

if ($isElevated) {
	$trigger = New-ScheduledTaskTrigger -AtStartup
	$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

	if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
		Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
	}

	Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Battery Health Analyzer logger'

	Write-Host "Installed scheduled task: $taskName"
} else {
	$startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
	$startupLauncher = Join-Path $startupDir 'Battery Health Analyzer Logger.cmd'
	$startupContent = @"
@echo off
start "" /min "$loggerWrapper" "$historyFile"
"@
	Set-Content -Path $startupLauncher -Value $startupContent -Encoding ASCII
	Write-Host "Installed startup launcher: $startupLauncher"
}

Write-Host "Installed desktop shortcut: Battery Health Analyzer.lnk"
