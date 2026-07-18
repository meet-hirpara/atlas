@echo off

cd /d "%~dp0backend"

where uv >nul 2>&1
if errorlevel 1 (
  echo [ERROR] uv is not installed. Run: python -m pip install uv
  exit /b 1
)

uv sync --quiet

REM Stop any stale listeners on port 8000 (reloader workers often orphan)
powershell -NoProfile -Command "$pids = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }"

timeout /t 2 /nobreak >nul 2>&1

REM Single process (no --reload) avoids zombie uvicorn workers on Windows
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
