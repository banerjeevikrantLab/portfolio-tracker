@echo off
cd /d "%~dp0backend"
echo Installing backend dependencies...

set PY=
where py >nul 2>&1 && set PY=py
if not defined PY where python >nul 2>&1 && set PY=python
if not defined PY where python3 >nul 2>&1 && set PY=python3

if defined PY (
    %PY% -m pip install -r requirements.txt
) else (
    echo Python not found. Install from python.org and add to PATH.
    pause
    exit /b 1
)

echo.
echo Installing frontend dependencies...
cd /d "%~dp0frontend"
if exist "node_modules" (
    echo node_modules exists, skipping npm install
) else (
    call npm install
)

echo.
echo Setup complete. Run start-backend.bat and start-frontend.bat in separate windows.
pause
