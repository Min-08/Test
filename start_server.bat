@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Simple launcher for the FastAPI backend on Windows
rem Usage: double-click or run `start_server.bat [PORT]`

set PORT=8000
if not "%1"=="" set PORT=%1

rem Prefer local virtual environment if present
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)

set PYTHONUTF8=1
echo Starting backend on http://127.0.0.1:%PORT% (Ctrl+C to stop)

python -m uvicorn backend.app:app --reload --port %PORT%

endlocal
