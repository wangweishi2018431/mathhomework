param(
    [int]$Port = 18080,
    [string]$BindHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

function Get-ListeningPids {
    param([int]$TargetPort)

    $pids = @()
    $pattern = ":$TargetPort\s+.*LISTENING\s+(\d+)$"
    $lines = netstat -ano | Select-String -Pattern $pattern

    foreach ($line in $lines) {
        $text = ($line.ToString() -replace "\s+", " ").Trim()
        $parts = $text.Split(" ")
        $pid = $parts[-1]

        if ($pid -match "^\d+$") {
            $pids += [int]$pid
        }
    }

    return $pids | Sort-Object -Unique
}

function Stop-PortProcesses {
    param([int]$TargetPort)

    $pids = Get-ListeningPids -TargetPort $TargetPort
    if (-not $pids -or $pids.Count -eq 0) {
        Write-Host "No listening process found on port $TargetPort"
        return
    }

    foreach ($pid in $pids) {
        if ($pid -eq $PID) {
            continue
        }

        Write-Host "Stopping PID $pid on port $TargetPort..."
        taskkill /PID $pid /F | Out-Null
    }
}

function Test-Runner {
    param([string[]]$Candidate)

    $args = @()
    if ($Candidate.Length -gt 1) {
        $args += $Candidate[1..($Candidate.Length - 1)]
    }
    $args += "--version"

    try {
        & $Candidate[0] @args *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-UvicornCommand {
    $venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"

    $candidates = @(
        @($venvPython, "-m", "uvicorn"),
        @("py", "-m", "uvicorn"),
        @("python", "-m", "uvicorn"),
        @("uvicorn")
    )

    foreach ($candidate in $candidates) {
        $commandName = $candidate[0]
        $exists = $false

        if ($commandName -like "*\\*" -or $commandName -like "*:*") {
            $exists = Test-Path $commandName
        } else {
            $exists = [bool](Get-Command $commandName -ErrorAction SilentlyContinue)
        }

        if (-not $exists) {
            continue
        }

        if (Test-Runner -Candidate $candidate) {
            return $candidate
        }
    }

    throw "No available Python/uvicorn command found."
}

Stop-PortProcesses -TargetPort $Port

$cmd = Resolve-UvicornCommand
$entry = "app.main:app"
$args = @($entry, "--host", $BindHost, "--port", "$Port", "--reload", "--reload-dir", "app")

$fullArgs = @()
if ($cmd.Length -gt 1) {
    $fullArgs += $cmd[1..($cmd.Length - 1)]
}
$fullArgs += $args

Write-Host "Starting backend at http://$BindHost`:$Port"
& $cmd[0] @fullArgs

