param(
    [string]$Token = "",
    [int]$Port = 8765,
    [string]$TailscaleIp = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $scriptDir ".runtime"
$runtimeInfoPath = Join-Path $logDir "yt_sync_runtime.json"
$runtimeCopyPath = Join-Path $logDir "yt_sync_runtime_copy.txt"
$serverScript = Join-Path $scriptDir "yt_sync_remote_server.py"

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

    throw "Nao encontrei um python.exe instalado."
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
    return "https://music.youtube.com/?yt_sync_bootstrap=$([uri]::EscapeDataString($payloadBase64))"
}

function Get-TailscaleExe {
    $cmd = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $candidates = @(
        "$env:ProgramFiles\Tailscale\tailscale.exe",
        "$env:LocalAppData\Tailscale\tailscale.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-TailscaleIpv4 {
    $tailscaleExe = Get-TailscaleExe
    if (-not $tailscaleExe) {
        return $null
    }

    try {
        $output = & $tailscaleExe ip -4 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }

        $lines = @($output | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' })
        if ($lines.Count -gt 0) {
            return $lines[0].Trim()
        }
    } catch {
    }

    return $null
}

function Test-ServerHealth {
    param(
        [string]$Url,
        [int]$Retries = 10,
        [int]$DelayMs = 1000
    )

    for ($i = 0; $i -lt $Retries; $i++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri ($Url.TrimEnd('/') + "/health") -TimeoutSec 5
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

if ([string]::IsNullOrWhiteSpace($Token)) {
    $Token = New-RandomToken
}

if ([string]::IsNullOrWhiteSpace($TailscaleIp)) {
    $TailscaleIp = Get-TailscaleIpv4
}

if ([string]::IsNullOrWhiteSpace($TailscaleIp)) {
    throw "Nao consegui descobrir o IP do Tailscale. Abra o Tailscale, confirme login, ou rode este script com -TailscaleIp."
}

if (!(Test-Path $serverScript)) {
    throw "Nao encontrei o servidor em $serverScript"
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

Remove-Item $runtimeInfoPath -Force -ErrorAction SilentlyContinue

$publicUrl = "http://$TailscaleIp`:$Port"
$serverCommand = "& { " +
    "`$env:YT_SYNC_TOKEN = '$Token'; " +
    "`$env:YT_SYNC_PORT = '$Port'; " +
    "`$env:YT_SYNC_HOST = '0.0.0.0'; " +
    "`$env:YT_SYNC_PUBLIC_URL = '$publicUrl'; " +
    "& '$pythonExe' '$serverScript' " +
    "}"

$serverProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-NoExit", "-Command", $serverCommand) `
    -WindowStyle Normal `
    -PassThru
$healthOk = Test-ServerHealth -Url $publicUrl -Retries 12 -DelayMs 1000

$hostSetupUrl = New-BootstrapUrl -ServerUrl $publicUrl -TokenValue $Token -RoleValue "host"
$clientSetupUrl = New-BootstrapUrl -ServerUrl $publicUrl -TokenValue $Token -RoleValue "client"

@{
    public_url = $publicUrl
    token = $Token
    host_setup_url = $hostSetupUrl
    client_setup_url = $clientSetupUrl
    tunnel_mode = "tailscale"
    generated_at = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json | Set-Content -Path $runtimeInfoPath -Encoding UTF8

Get-Content $runtimeInfoPath -Raw | Set-Content -Path $runtimeCopyPath -Encoding UTF8

Write-Host ""
Write-Host "YT Sync Host iniciado via Tailscale." -ForegroundColor Green
Write-Host ("Servidor PID: " + $serverProcess.Id)
Write-Host ("IP Tailscale: " + $TailscaleIp) -ForegroundColor Cyan
Write-Host ("Server URL: " + $publicUrl) -ForegroundColor Cyan
Write-Host ("Token: " + $Token) -ForegroundColor Cyan
Write-Host ("Health: " + ($(if ($healthOk) { "ok" } else { "falhou" })))
Write-Host ""
Write-Host "URL de setup do host:" -ForegroundColor Green
Write-Host $hostSetupUrl -ForegroundColor Cyan
Write-Host ""
Write-Host "URL de setup do client:" -ForegroundColor Green
Write-Host $clientSetupUrl -ForegroundColor Cyan
Write-Host ""
Write-Host ("Runtime salvo em: " + $runtimeInfoPath)
Write-Host ("Runtime para copiar: " + $runtimeCopyPath)

if (-not $NoBrowser) {
    Start-Process $hostSetupUrl | Out-Null
    Write-Host ""
    Write-Host "Abrindo a URL de setup do host no navegador..." -ForegroundColor Green
}

Write-Host ""
Write-Host "Deixe a janela do servidor aberta."
