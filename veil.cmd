@echo off
setlocal
set ROOT=%~dp0

where uv >nul 2>&1
if %ERRORLEVEL%==0 (
  uv --directory "%ROOT%." sync
  uv --directory "%ROOT%." run python "%ROOT%main.py" %*
  exit /b %ERRORLEVEL%
)

if not exist "%ROOT%.venv\Scripts\python.exe" (
  echo [veil] uv not found; creating .venv with python -m venv ...
  python -m venv "%ROOT%.venv"
  "%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
)

"%ROOT%.venv\Scripts\python.exe" "%ROOT%main.py" %*