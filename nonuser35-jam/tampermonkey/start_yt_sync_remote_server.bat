@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=python"

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)

if "%YT_SYNC_TOKEN%"=="" (
    set "YT_SYNC_TOKEN=troque-este-token"
)

echo Iniciando YT Sync Remote Server...
echo Python: %PYTHON_EXE%
echo Porta: %YT_SYNC_PORT%
echo Token: %YT_SYNC_TOKEN%
echo.

"%PYTHON_EXE%" "%SCRIPT_DIR%yt_sync_remote_server.py"

endlocal
