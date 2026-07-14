@echo off
setlocal

rem Unified PostgreSQL + authentication platform entrypoint.
rem start_quota_building.cmd and start_quota_a111.cmd are legacy prototype only.
cd /d "%~dp0"

set "PYTHON=%~dp0data\private\platform_dev\.venv\Scripts\python.exe"
set "ENV_FILE=%~dp0.env.platform.local"

if not exist "%PYTHON%" (
  echo [ERROR] Platform Python runtime is unavailable.
  exit /b 1
)

if not exist "%ENV_FILE%" (
  echo [ERROR] Missing environment variables: PLATFORM_TENANT_CODE, PLATFORM_BOOTSTRAP_ADMIN_USERNAME, PLATFORM_BOOTSTRAP_ADMIN_DISPLAY_NAME, PLATFORM_BOOTSTRAP_ADMIN_PASSWORD, PLATFORM_UAT_TEMP_PASSWORD, SESSION_COOKIE_SECURE
  exit /b 3
)

"%PYTHON%" -m platform_db.local_runtime --env-file "%ENV_FILE%" --host 127.0.0.1 --port 8006
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
