$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $root ".runtime\service-pids.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No PID file found at $pidFile"
    exit 0
}

$entries = Get-Content $pidFile -Raw | ConvertFrom-Json
if ($entries -isnot [System.Array]) {
    $entries = @($entries)
}

foreach ($entry in $entries) {
    $procId = [int]$entry.pid
    try {
        Get-Process -Id $procId -ErrorAction Stop | Out-Null
        Stop-Process -Id $procId -Force
        Write-Host ("Stopped {0} (PID {1})" -f $entry.name, $procId)
    } catch {
        Write-Host ("Not running: {0} (PID {1})" -f $entry.name, $procId)
    }
}

Remove-Item $pidFile -Force
Write-Host "Removed PID file."
