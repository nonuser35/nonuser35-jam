param(
    [string]$Token = "",
    [int]$Port = 8765,
    [string]$TunnelToken = "",
    [string]$PublicUrl = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir
$serverScript = Join-Path $scriptDir "yt_sync_remote_server.py"
$cloudflaredExe = Join-Path $rootDir "projeto\cloudflared-windows-amd64.exe"
$logDir = Join-Path $scriptDir ".runtime"
$cloudflaredOut = Join-Path $logDir "cloudflared.out.log"
$cloudflaredErr = Join-Path $logDir "cloudflared.err.log"
$runtimeInfoPath = Join-Path $logDir "yt_sync_runtime.json"
$tunnelMode = "trycloudflare"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

function Get-PythonExe {
    $candidates = @(
        "$env:LocalAppData\Programs\Python\Python312\python.exe",
        "$env:LocalAppData\Programs\Python\Python311\python.exe",
        "$env:LocalAppData\Programs\Python\Python310\python.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Nao encontrei um python.exe instalado em LocalAppData\\Programs\\Python."
}

function New-RandomToken {
    $chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    -join (1..24 | ForEach-Object { $chars[(Get-Random -Minimum 0 -Maximum $chars.Length)] })
}

function New-BootstrapUrl {
    param(
        [string]$ServerUrl,
        [string]$TokenValue,
        [string]$RoleValue
    )

    $payloadObject = @{
        server = $ServerUrl
        token = $TokenValue
        role = $RoleValue
    }
    $payloadJson = $payloadObject | ConvertTo-Json -Compress
    $payloadBase64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($payloadJson))
    return "https://music.youtube.com/#yt-sync-bootstrap=$([uri]::EscapeDataString($payloadBase64))"
}

function Test-PublicUrlHealth {
    param(
        [string]$Url,
        [int]$Retries = 1,
        [int]$DelayMs = 1000
    )

    if ([string]::IsNullOrWhiteSpace($Url)) {
        return $false
    }

    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $healthUrl = $Url.TrimEnd('/') + "/health"
            $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return $true
            }
        } catch {
        }

        if ($i -lt ($Retries - 1)) {
            Start-Sleep -Milliseconds $DelayMs
        }
    }

    return $false
}

function Get-TryCloudflareUrlFromContent {
    param(
        [string]$Content
    )

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $null
    }

    $matches = [regex]::Matches($Content, 'https://[-a-z0-9]+\.trycloudflare\.com')
    if ($matches.Count -gt 0) {
        return $matches[$matches.Count - 1].Value.TrimEnd('/')
    }

    return $null
}

if ([string]::IsNullOrWhiteSpace($Token)) {
    $Token = New-RandomToken
}

if ([string]::IsNullOrWhiteSpace($TunnelToken) -and $env:YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN) {
    $TunnelToken = $env:YT_SYNC_CLOUDFLARED_TUNNEL_TOKEN
}

if ([string]::IsNullOrWhiteSpace($PublicUrl) -and $env:YT_SYNC_PUBLIC_URL) {
    $PublicUrl = $env:YT_SYNC_PUBLIC_URL
}

if (!(Test-Path $serverScript)) {
    throw "Nao encontrei o servidor em $serverScript"
}

if (!(Test-Path $cloudflaredExe)) {
    throw "Nao encontrei o cloudflared em $cloudflaredExe"
}

$pythonExe = Get-PythonExe

$existingServer = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -eq "python.exe" -and $_.CommandLine -like "*yt_sync_remote_server.py*"
}
if ($existingServer) {
    Write-Host "Encerrando servidor YT Sync antigo..." -ForegroundColor Yellow
    $existingServer | ForEach-Object {
        Write-Host ("Finalizando PID servidor: " + $_.ProcessId)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

$existingTunnel = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like "cloudflared*" -and
    (
        ($_.CommandLine -like "*localhost:$Port*") -or
        ($_.CommandLine -like "*--token*") -or
        ($_.CommandLine -like "*tunnel run*")
    )
}
if ($existingTunnel) {
    Write-Host "Encerrando cloudflared antigo..." -ForegroundColor Yellow
    $existingTunnel | ForEach-Object {
        Write-Host ("Finalizando PID tunnel: " + $_.ProcessId)
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

Remove-Item $cloudflaredOut, $cloudflaredErr -Force -ErrorAction SilentlyContinue
Remove-Item $runtimeInfoPath -Force -ErrorAction SilentlyContinue

$serverCommand = "& { " +
    "`$env:YT_SYNC_TOKEN = '$Token'; " +
    "`$env:YT_SYNC_PORT = '$Port'; " +
    "& '$pythonExe' '$serverScript' " +
    "}"

$serverProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoExit", "-Command", $serverCommand) `
    -WindowStyle Normal `
    -PassThru

Start-Sleep -Seconds 2

$cloudflaredArgs = @("tunnel", "--url", "http://localhost:$Port")
if (-not [string]::IsNullOrWhiteSpace($TunnelToken)) {
    $cloudflaredArgs = @("tunnel", "run", "--token", $TunnelToken)
    $tunnelMode = "named"
}

$cloudflaredProcess = Start-Process -FilePath $cloudflaredExe `
    -ArgumentList $cloudflaredArgs `
    -RedirectStandardOutput $cloudflaredOut `
    -RedirectStandardError $cloudflaredErr `
    -WindowStyle Hidden `
    -PassThru

$publicUrl = $null
$deadline = (Get-Date).AddSeconds(45)

if (-not [string]::IsNullOrWhiteSpace($PublicUrl)) {
    $publicUrl = $PublicUrl.Trim().TrimEnd('/')
}

while ((Get-Date) -lt $deadline) {
    if ($publicUrl) {
        break
    }

    foreach ($logFile in @($cloudflaredOut, $cloudflaredErr)) {
        if (Test-Path $logFile) {
            $content = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
            if ($content) {
                if ($tunnelMode -eq "named" -and -not [string]::IsNullOrWhiteSpace($PublicUrl)) {
                    $candidateUrl = $PublicUrl.Trim().TrimEnd('/')
                    if (Test-PublicUrlHealth -Url $candidateUrl -Retries 1 -DelayMs 300) {
                        $publicUrl = $candidateUrl
                        break
                    }
                } else {
                    $candidateUrl = Get-TryCloudflareUrlFromContent -Content $content
                    if ($candidateUrl) {
                        $publicUrl = $candidateUrl
                        break
                    }
                }
            }
        }
    }
    if ($publicUrl) {
        break
    }
    Start-Sleep -Milliseconds 700
}

if ($publicUrl -and -not (Test-PublicUrlHealth -Url $publicUrl -Retries 20 -DelayMs 1000)) {
    Write-Host "Tunnel encontrado, mas /health ainda nao respondeu a tempo. Vou continuar com a URL mesmo assim." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "YT Sync Host iniciado." -ForegroundColor Green
Write-Host ("Servidor PID: " + $serverProcess.Id)
Write-Host ("Cloudflared PID: " + $cloudflaredProcess.Id)
Write-Host ("Modo tunnel: " + $tunnelMode)
Write-Host ("Token: " + $Token) -ForegroundColor Cyan
if ($publicUrl) {
    Write-Host ("URL publica: " + $publicUrl) -ForegroundColor Cyan
} else {
    Write-Host "Nao consegui capturar a URL publica automaticamente ainda." -ForegroundColor Yellow
    Write-Host ("Veja o log: " + $cloudflaredOut)
    Write-Host ("Ou o log: " + $cloudflaredErr)
}
Write-Host ""
Write-Host "Use no script remoto:" -ForegroundColor Green
$serverUrlDisplay = "veja o log acima"
if ($publicUrl) {
    $serverUrlDisplay = $publicUrl
}
Write-Host ("Server URL = " + $serverUrlDisplay)
Write-Host ("Token = " + $Token)
if ($publicUrl) {
    $setupUrl = New-BootstrapUrl -ServerUrl $publicUrl -TokenValue $Token -RoleValue "host"
    $clientSetupUrl = New-BootstrapUrl -ServerUrl $publicUrl -TokenValue $Token -RoleValue "client"
    @{
        public_url = $publicUrl
        token = $Token
        host_setup_url = $setupUrl
        client_setup_url = $clientSetupUrl
        tunnel_mode = $tunnelMode
        generated_at = [DateTime]::UtcNow.ToString("o")
    } | ConvertTo-Json | Set-Content -Path $runtimeInfoPath -Encoding UTF8
    Write-Host ""
    Write-Host "URL de setup do host:" -ForegroundColor Green
    Write-Host $setupUrl -ForegroundColor Cyan
    Write-Host ""
    Write-Host "URL de setup do client:" -ForegroundColor Green
    Write-Host $clientSetupUrl -ForegroundColor Cyan

    if (-not $NoBrowser) {
        Start-Process $setupUrl | Out-Null
        Write-Host ""
        Write-Host "Abrindo a URL de setup do host no navegador..." -ForegroundColor Green
    }
}
Write-Host ""
Write-Host "Deixe a janela do servidor aberta. Para parar tudo, feche a janela do servidor e finalize o processo cloudflared PID $($cloudflaredProcess.Id) se necessario."
if (Test-Path $runtimeInfoPath) {
    Write-Host ("Runtime salvo em: " + $runtimeInfoPath)
}
