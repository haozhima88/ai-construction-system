@echo off
setlocal

set "ENGINE_ROOT=%~dp0"
for %%I in ("%ENGINE_ROOT%..") do set "PROJECT_ROOT=%%~fI"
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"
set "PORT=8006"

if not exist "%PYTHON%" (
  echo [ERROR] Project virtual environment not found: %PYTHON%
  exit /b 1
)

netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
  echo [ERROR] Port %PORT% is already in use. Stop the existing listener or choose another port.
  exit /b 2
)

cd /d "%PROJECT_ROOT%"
start "" "http://127.0.0.1:%PORT%/quota-building"
echo Starting quota-building review workspace at http://127.0.0.1:%PORT%/quota-building
"%PYTHON%" -m uvicorn web_collab_prototype.app:app --app-dir "%ENGINE_ROOT%" --host 127.0.0.1 --port %PORT%

endlocal
