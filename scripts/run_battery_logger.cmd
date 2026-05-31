@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
set "OUTPUT_FILE=%PROJECT_DIR%\battery_history.csv"
if not "%~1"=="" (
	set "OUTPUT_FILE=%~1"
)
if "%BATTERY_LOGGER_INTERVAL_SECONDS%"=="" (
	set "INTERVAL_SECONDS=60"
) else (
	set "INTERVAL_SECONDS=%BATTERY_LOGGER_INTERVAL_SECONDS%"
)

where py >nul 2>nul
if not errorlevel 1 (
	py -3 "%PROJECT_DIR%\battery_logger.py" --loop --interval-seconds %INTERVAL_SECONDS% --output "%OUTPUT_FILE%"
	exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
	python "%PROJECT_DIR%\battery_logger.py" --loop --interval-seconds %INTERVAL_SECONDS% --output "%OUTPUT_FILE%"
	exit /b %errorlevel%
)

echo Python was not found in PATH.
exit /b 1
