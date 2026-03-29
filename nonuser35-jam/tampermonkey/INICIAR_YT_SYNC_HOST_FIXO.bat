@echo off
setlocal

if "%YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN%"=="" (
  echo Defina antes a variavel YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN com o token do tunnel nomeado.
  echo Opcionalmente defina YT_SYNC_PUBLIC_URL com a URL fixa, ex: https://sync.seudominio.com
  echo.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { & '%~dp0start_yt_sync_remote_host.ps1' -TunnelToken $env:YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN -PublicUrl $env:YT_SYNC_PUBLIC_URL } catch { Write-Host ''; Write-Host 'ERRO:' -ForegroundColor Red; Write-Host $_.Exception.Message -ForegroundColor Red }"

echo.
pause

endlocal
