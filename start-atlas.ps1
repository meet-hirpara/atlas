# Atlas: backend + frontend in one terminal ([BE]/[FE] logs, Ctrl+C stops both)
$Root = $PSScriptRoot
$script:ChildProcs = @()

function Stop-PortListeners {
    param([int]$Port)
    $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne 0) {
            Write-Host "[atlas] Stopping PID $procId on port $Port"
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Stop-AtlasChildren {
    foreach ($p in $script:ChildProcs) {
        if ($p -and -not $p.HasExited) {
            try { $p.Kill($true) } catch { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
        }
    }
    Stop-PortListeners -Port 8000
    Stop-PortListeners -Port 5173
}

function Start-PrefixedProcess {
    param(
        [string]$Prefix,
        [string]$FileName,
        [string]$Arguments,
        [string]$WorkingDirectory
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FileName
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $null = $proc.add_OutputDataReceived({ param($s, $e) if ($null -ne $e.Data) { Write-Host "[$Prefix] $($e.Data)" } })
    $null = $proc.add_ErrorDataReceived({ param($s, $e) if ($null -ne $e.Data) { Write-Host "[$Prefix] $($e.Data)" } })
    [void]$proc.Start()
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    $script:ChildProcs += $proc
    return $proc
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[atlas] ERROR: uv is not installed. Run: python -m pip install uv"
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "[atlas] ERROR: npm is not installed."
    exit 1
}

Write-Host "[atlas] Stopping stale listeners on 8000 and 5173..."
Stop-PortListeners -Port 8000
Stop-PortListeners -Port 5173
Start-Sleep -Seconds 2

$backendDir = Join-Path $Root "backend"
$frontendDir = Join-Path $Root "frontend"

Write-Host "[atlas] Syncing backend dependencies..."
Push-Location $backendDir
& uv sync --quiet 2>&1 | ForEach-Object { Write-Host "[BE] $_" }
$syncCode = $LASTEXITCODE
Pop-Location
if ($syncCode -ne 0) { exit $syncCode }

Write-Host "[atlas] Starting backend (http://127.0.0.1:8000) and frontend (http://localhost:5173)..."
Write-Host "[atlas] Press Ctrl+C to stop both."

[Console]::TreatControlCAsInput = $false
$null = [Console]::CancelKeyPress.Add({
    param($sender, $e)
    $e.Cancel = $true
    Write-Host ""
    Write-Host "[atlas] Ctrl+C received, stopping..."
    Stop-AtlasChildren
    exit 0
})

$beProc = Start-PrefixedProcess -Prefix "BE" -FileName "cmd.exe" -Arguments "/c uv run uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $backendDir
$feProc = Start-PrefixedProcess -Prefix "FE" -FileName "cmd.exe" -Arguments "/c npm run dev" -WorkingDirectory $frontendDir

try {
    while (-not $beProc.HasExited -and -not $feProc.HasExited) {
        Start-Sleep -Milliseconds 400
    }
    if ($beProc.HasExited) { Write-Host "[atlas] Backend exited (code $($beProc.ExitCode))." }
    if ($feProc.HasExited) { Write-Host "[atlas] Frontend exited (code $($feProc.ExitCode))." }
}
finally {
    Stop-AtlasChildren
}


