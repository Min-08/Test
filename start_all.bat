@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Launch both backend (FastAPI) and frontend (static server) in separate windows.
rem Usage: double-click or run `start_all.bat [BACKEND_PORT] [FRONTEND_PORT]`

set BACKEND_PORT=8000
set FRONTEND_PORT=5500

if not "%1"=="" set BACKEND_PORT=%1
if not "%2"=="" set FRONTEND_PORT=%2

rem Activate venv for backend if present
if exist .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)

set PYTHONUTF8=1

echo Launching backend on http://127.0.0.1:%BACKEND_PORT%
start "backend" cmd /c python -m uvicorn backend.app:app --reload --port %BACKEND_PORT%

echo Launching frontend on http://127.0.0.1:%FRONTEND_PORT%
start "frontend" cmd /c python -m http.server %FRONTEND_PORT% -d frontend

echo Both servers launched. Press any key to close this window.
pause >nul

endlocal

