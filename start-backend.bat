@echo off
cd /d "%~dp0backend"

REM Try py (Windows launcher), then python, then python3
where py >nul 2>&1 && (
    py app.py
) || where python >nul 2>&1 && (
    python app.py
) || where python3 >nul 2>&1 && (
    python3 app.py
) || (
    echo Python not found. Add Python to PATH or install from python.org
    pause
)
