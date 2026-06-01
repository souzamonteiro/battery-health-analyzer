@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"
if "%~1"=="" (
	set "DATA_FILE=%PROJECT_DIR%\battery_data.bdf.csv"
) else (
	set "DATA_FILE=%~1"
)

where pythonw >nul 2>nul
if not errorlevel 1 (
	if exist "%DATA_FILE%" (
		pythonw "%PROJECT_DIR%\battery_bdf_analyzer.py" "%DATA_FILE%"
	) else (
		pythonw "%PROJECT_DIR%\battery_bdf_analyzer.py"
	)
	exit /b %errorlevel%
)

where py >nul 2>nul
if not errorlevel 1 (
	if exist "%DATA_FILE%" (
		py -3 "%PROJECT_DIR%\battery_bdf_analyzer.py" "%DATA_FILE%"
	) else (
		py -3 "%PROJECT_DIR%\battery_bdf_analyzer.py"
	)
	exit /b %errorlevel%
)

where python >nul 2>nul
if not errorlevel 1 (
	if exist "%DATA_FILE%" (
		python "%PROJECT_DIR%\battery_bdf_analyzer.py" "%DATA_FILE%"
	) else (
		python "%PROJECT_DIR%\battery_bdf_analyzer.py"
	)
	exit /b %errorlevel%
)

echo Python was not found in PATH.
exit /b 1
