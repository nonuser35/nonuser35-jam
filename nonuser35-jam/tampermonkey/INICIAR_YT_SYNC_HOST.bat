@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { & '%~dp0start_yt_sync_remote_host.ps1' } catch { Write-Host ''; Write-Host 'ERRO:' -ForegroundColor Red; Write-Host $_.Exception.Message -ForegroundColor Red }"

echo.
pause

endlocal
