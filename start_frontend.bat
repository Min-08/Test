@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Simple launcher for the static frontend on Windows
rem Usage: double-click or run `start_frontend.bat [PORT]`

set PORT=5500
if not "%1"=="" set PORT=%1

echo Starting frontend on http://127.0.0.1:%PORT% (Ctrl+C to stop)

python -m http.server %PORT% -d frontend

endlocal

