$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir '..')).Path
$historyFile = Join-Path $projectDir 'battery_data.bdf.csv'
$loggerScript = Join-Path $projectDir 'battery_bdf_collector.py'
$analyzerScript = Join-Path $projectDir 'battery_bdf_analyzer.py'
$analyzerWrapper = Join-Path $scriptDir 'open_battery_health_analyzer.cmd'
$requirementsFile = Join-Path $projectDir 'requirements.txt'
$taskName = 'BatteryHealthAnalyzerLogger'
$metricMode = 'health'


function Test-Administrator {
	$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
	$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
	return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}


$loggerPythonCandidates = @('py', 'python')
$loggerPythonExe = $null
$loggerPythonArgs = @()
foreach ($candidate in $loggerPythonCandidates) {
	$cmd = Get-Command $candidate -ErrorAction SilentlyContinue
	if ($cmd) {
		$loggerPythonExe = $cmd.Source
		if ($candidate -eq 'py') {
			$loggerPythonArgs = @('-3')
		}
		break
	}
}

if (-not $loggerPythonExe) {
	throw 'Python was not found in PATH.'
}

$guiPythonCandidates = @('pythonw', 'pyw', 'py', 'python')
$guiPythonExe = $null
$guiPythonArgs = @()
foreach ($candidate in $guiPythonCandidates) {
	$cmd = Get-Command $candidate -ErrorAction SilentlyContinue
	if ($cmd) {
		$guiPythonExe = $cmd.Source
		if ($candidate -eq 'pyw' -or $candidate -eq 'py') {
			$guiPythonArgs = @('-3')
		}
		break
	}
}

if (-not $guiPythonExe) {
	$guiPythonExe = $loggerPythonExe
}

if (-not (Test-Path $analyzerWrapper)) {
	throw "Missing wrapper: $analyzerWrapper"
}

# Ensure collector dependency exists in the interpreter used by the task.
try {
	$installPsutilArgs = @()
	$installPsutilArgs += $loggerPythonArgs
	$installPsutilArgs += @('-m', 'pip', 'install', '--disable-pip-version-check', 'psutil')
	& $loggerPythonExe @installPsutilArgs | Out-Host
} catch {
	Write-Warning "Could not install psutil automatically: $($_.Exception.Message)"
}

$isElevated = Test-Administrator

$desktopPath = [Environment]::GetFolderPath('Desktop')
if (-not [string]::IsNullOrWhiteSpace($desktopPath)) {
	$wsh = New-Object -ComObject WScript.Shell
	$shortcutPath = Join-Path $desktopPath 'Battery Health Analyzer.lnk'
	$shortcut = $wsh.CreateShortcut($shortcutPath)
	$shortcut.TargetPath = $guiPythonExe
	$shortcutArgParts = @()
	$shortcutArgParts += $guiPythonArgs
	$shortcutArgParts += @("`"$analyzerScript`"", "`"$historyFile`"")
	$shortcut.Arguments = ($shortcutArgParts -join ' ')
	$shortcut.WorkingDirectory = $projectDir
	$shortcut.Description = 'Open BDF Battery Analyzer with the default collector dataset'
	$shortcut.IconLocation = "$guiPythonExe,0"
	$shortcut.Save()
}

$taskArgParts = @()
$taskArgParts += $loggerPythonArgs
$taskArgParts += @("`"$loggerScript`"", '--loop', '--interval', '60', '--output', "`"$historyFile`"")
$action = New-ScheduledTaskAction -Execute $loggerPythonExe -Argument ($taskArgParts -join ' ') -WorkingDirectory $projectDir
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
	Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

if ($isElevated) {
	$trigger = New-ScheduledTaskTrigger -AtStartup
	$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest

	Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Battery Health Analyzer logger'

	Write-Host "Installed scheduled task: $taskName"
} else {
	$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
	$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
	$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

	Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Battery Health Analyzer logger (user logon)'

	$startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
	$startupLauncher = Join-Path $startupDir 'Battery Health Analyzer Logger.cmd'
	if (Test-Path $startupLauncher) {
		Remove-Item $startupLauncher -Force
		Write-Host "Removed legacy startup launcher: $startupLauncher"
	}

	Write-Host "Installed scheduled task: $taskName (trigger: user logon)"
}

try {
	Start-ScheduledTask -TaskName $taskName
	Write-Host "Started scheduled task now: $taskName"
} catch {
	Write-Warning "Task installed but could not be started immediately: $($_.Exception.Message)"
}

Write-Host "Collector mode: BDF (health-oriented telemetry)"
Write-Host "Installed desktop shortcut: Battery Health Analyzer.lnk"
if (Test-Path $requirementsFile) {
	Write-Host "Requirements file detected: $requirementsFile"
}
