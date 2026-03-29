@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$runtimePath = '%~dp0.runtime\yt_sync_runtime.json';" ^
  "if (!(Test-Path $runtimePath)) { Write-Host 'Nao encontrei runtime atual. Rode primeiro INICIAR_YT_SYNC_HOST.bat' -ForegroundColor Red; exit 1 };" ^
  "$data = Get-Content $runtimePath -Raw | ConvertFrom-Json;" ^
  "if (-not $data.client_setup_url) { Write-Host 'Runtime sem client_setup_url.' -ForegroundColor Red; exit 1 };" ^
  "Start-Process $data.client_setup_url; Write-Host 'Abrindo client setup...' -ForegroundColor Green"

echo.
pause

endlocal
