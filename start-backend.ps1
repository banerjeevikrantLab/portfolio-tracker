# Run from project root
$backendDir = Join-Path $PSScriptRoot "backend"
Set-Location $backendDir

# Try py launcher first (Windows), then python
$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $python = "python3" }

if ($python) {
    & $python app.py
} else {
    Write-Host "Python not found. Add Python to PATH or install from python.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
