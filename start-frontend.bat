@echo off
cd /d "%~dp0frontend"

REM Try npm (comes with Node.js)
where npm >nul 2>&1 && (
    npm run dev
) || (
    echo npm not found. Install Node.js from nodejs.org
    pause
)
