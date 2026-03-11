param(
    [switch]$WithInfra,
    [int]$StartupTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

if ($WithInfra) {
    Write-Host "Starting optional Docker services..."
    docker compose up -d
}

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$runtimeDir = Join-Path $root ".runtime"
$logDir = Join-Path $runtimeDir "logs"
$pidFile = Join-Path $runtimeDir "service-pids.json"

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

if (Test-Path $pidFile) {
    Write-Warning "PID file already exists at $pidFile. Run .\scripts\stop_all.ps1 first if needed."
}

$services = @(
    [pscustomobject]@{
        Name = "order-service"
        Script = "apps/order-service/main.py"
        Health = "http://127.0.0.1:8002/health"
    },
    [pscustomobject]@{
        Name = "payment-service"
        Script = "apps/payment-service/main.py"
        Health = "http://127.0.0.1:8003/health"
    },
    [pscustomobject]@{
        Name = "ai-agent-service"
        Script = "apps/ai-agent-service/main.py"
        Health = "http://127.0.0.1:8001/health"
    },
    [pscustomobject]@{
        Name = "api-gateway"
        Script = "apps/api-gateway/main.py"
        Health = "http://127.0.0.1:8000/health"
    }
)

$started = @()
foreach ($service in $services) {
    $stdoutLog = Join-Path $logDir "$($service.Name).out.log"
    $stderrLog = Join-Path $logDir "$($service.Name).err.log"

    if (Test-Path $stdoutLog) { Remove-Item $stdoutLog -Force }
    if (Test-Path $stderrLog) { Remove-Item $stderrLog -Force }

    $proc = Start-Process `
        -FilePath $python `
        -ArgumentList $service.Script `
        -WorkingDirectory $root `
        -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    $started += [pscustomobject]@{
        name = $service.Name
        pid = $proc.Id
        script = $service.Script
        health = $service.Health
        out_log = $stdoutLog
        err_log = $stderrLog
    }

    Write-Host ("Started {0} (PID {1})" -f $service.Name, $proc.Id)
}

$started | ConvertTo-Json -Depth 5 | Set-Content -Path $pidFile -Encoding UTF8

function Test-Health {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

Write-Host ""
Write-Host "Waiting for health checks..."

$failed = $false
foreach ($service in $services) {
    $ok = Test-Health -Url $service.Health -TimeoutSeconds $StartupTimeoutSeconds
    if ($ok) {
        Write-Host ("OK   {0}" -f $service.Health) -ForegroundColor Green
    } else {
        Write-Host ("FAIL {0}" -f $service.Health) -ForegroundColor Red
        $failed = $true
    }
}

Write-Host ""
Write-Host "PID file: $pidFile"
Write-Host "Logs: $logDir"
Write-Host "Stop all services: .\scripts\stop_all.ps1"

if ($failed) {
    Write-Warning "One or more services failed health checks. Check logs and retry."
    exit 1
}
