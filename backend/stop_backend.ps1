param(
    [int]$Port = 18080
)

$pattern = ":$Port\s+.*LISTENING\s+(\d+)$"
$lines = netstat -ano | Select-String -Pattern $pattern
$pids = @()

foreach ($line in $lines) {
    $text = ($line.ToString() -replace "\s+", " ").Trim()
    $parts = $text.Split(" ")
    $pid = $parts[-1]

    if ($pid -match "^\d+$") {
        $pids += [int]$pid
    }
}

$pids = $pids | Sort-Object -Unique

if (-not $pids -or $pids.Count -eq 0) {
    Write-Host "No listening process found on port $Port"
    exit 0
}

foreach ($pid in $pids) {
    Write-Host "Stopping PID $pid on port $Port..."
    taskkill /PID $pid /F | Out-Null
}

Write-Host "Port $Port is now clean"
