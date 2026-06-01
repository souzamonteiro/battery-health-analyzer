@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
if "%~1"=="" (
	set "HISTORY_FILE=%PROJECT_DIR%\battery_history.csv"
) else (
	set "HISTORY_FILE=%~1"
)

where pythonw >nul 2>nul
if not errorlevel 1 (
	pythonw "%PROJECT_DIR%\battery_health_analyzer.py" "%HISTORY_FILE%"
	exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
	py -3 "%PROJECT_DIR%\battery_health_analyzer.py" "%HISTORY_FILE%"
	exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
	python "%PROJECT_DIR%\battery_health_analyzer.py" "%HISTORY_FILE%"
	exit /b %errorlevel%
)

echo Python was not found in PATH.
exit /b 1
