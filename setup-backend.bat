@echo off
setlocal

cd /d "%~dp0backend"

where uv >nul 2>&1
if errorlevel 1 (
  echo [ERROR] uv is not installed.
  echo Install: python -m pip install uv
  echo Or: https://docs.astral.sh/uv/getting-started/installation/
  exit /b 1
)

echo Syncing dependencies with uv...
uv sync --quiet
if errorlevel 1 exit /b 1

echo.
echo Backend ready. Start with: start-backend.bat
exit /b 0
