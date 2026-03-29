@echo off
setlocal

set "ROOT_DIR=%~dp0.."
set "CLOUDFLARED_EXE=%ROOT_DIR%\projeto\cloudflared-windows-amd64.exe"
set "YT_SYNC_PORT=8765"

if not exist "%CLOUDFLARED_EXE%" (
    echo Nao encontrei o cloudflared em:
    echo %CLOUDFLARED_EXE%
    pause
    exit /b 1
)

echo Publicando http://localhost:%YT_SYNC_PORT% com Cloudflare Tunnel...
echo.

"%CLOUDFLARED_EXE%" tunnel --url http://localhost:%YT_SYNC_PORT%

endlocal
