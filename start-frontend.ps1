# Run from project root
$frontendDir = Join-Path $PSScriptRoot "frontend"
Set-Location $frontendDir

if (Get-Command npm -ErrorAction SilentlyContinue) {
    npm run dev
} else {
    Write-Host "npm not found. Install Node.js from nodejs.org" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
