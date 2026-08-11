@echo off
setlocal

REM Resolve project root, script lives in scripts folder
set ROOT=%~dp0..
for %%i in ("%ROOT%") do set "ROOT=%%~fi"

set PY=%ROOT%\backend\venv\Scripts\python.exe

echo ==========================================================
echo   ai-creator local dev launcher
echo ==========================================================
echo.

REM Pre-checks: MySQL and Memurai services
sc query MySQL80 | find "RUNNING" >nul || (
    echo [ERROR] MySQL service MySQL80 is not running.
    pause
    exit /b 1
)
sc query Memurai | find "RUNNING" >nul || (
    echo [ERROR] Memurai Redis service is not running.
    pause
    exit /b 1
)

REM Dependency checks
if not exist "%PY%" (
    echo [ERROR] Backend venv not found: %PY%
    echo         Run: cd backend ^&^& python -m venv venv ^&^& pip install -r requirements.txt
    pause
    exit /b 1
)
if not exist "%ROOT%\frontend\node_modules" (
    echo [ERROR] Frontend dependencies missing. Run: cd frontend ^&^& npm install
    pause
    exit /b 1
)
if not exist "%ROOT%\backend\.env" (
    echo [INFO] .env not found, copying from .env.example...
    copy "%ROOT%\backend\.env.example" "%ROOT%\backend\.env" >nul
)

REM Start backend, port 8000 (health check first; restart if stale)
curl -s -o nul --max-time 3 http://localhost:8000/docs
if errorlevel 1 (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
    echo [1/2] Starting backend window ai-creator-backend...
    start "ai-creator-backend" cmd /k "cd /d %ROOT%\backend && %PY% run.py"
) else (
    echo [1/2] Skipped: backend already responding on port 8000.
)

REM Start frontend, port 5173 (health check first; restart if stale)
curl -s -o nul --max-time 3 http://localhost:5173/
if errorlevel 1 (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
    echo [2/2] Starting frontend Vite window ai-creator-frontend...
    start "ai-creator-frontend" cmd /k "cd /d %ROOT%\frontend && npm.cmd run dev -- --host 0.0.0.0"
) else (
    echo [2/2] Skipped: frontend already responding on port 5173.
)

echo.
echo Waiting for services to start, about 15 seconds...
ping -n 16 127.0.0.1 >nul

echo.
echo ==========================================================
echo   Service status
echo ==========================================================
curl -s -o nul -w "  - Frontend Vite   http://localhost:5173          HTTP %%{http_code}\n" http://localhost:5173/
curl -s -o nul -w "  - Backend API     http://localhost:8000          HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - Swagger         http://localhost:8000/docs     HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - OpenAPI         http://localhost:8000/openapi.json  HTTP %%{http_code}\n" http://localhost:8000/openapi.json

echo.
echo ==========================================================
echo   Debug entries
echo ==========================================================
echo   Browser:      http://localhost:5173
echo   Swagger:      http://localhost:8000/docs
echo   Test account: admin / admin123456

REM Detect LAN IP for mobile debugging (adapter with default gateway)
set "LAN_IP="
powershell -NoProfile -Command "[System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | Where-Object { $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up -and $_.NetworkInterfaceType -ne [System.Net.NetworkInformation.NetworkInterfaceType]::Loopback -and $_.NetworkInterfaceType -ne [System.Net.NetworkInformation.NetworkInterfaceType]::Tunnel } | ForEach-Object { $ip=$_.GetIPProperties(); if ($ip.GatewayAddresses.Count -gt 0) { foreach ($u in $ip.UnicastAddresses) { if ($u.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) { $b=$u.Address.GetAddressBytes(); if ($b[0] -ne 127 -and $b[0] -ne 169) { $u.Address.ToString() } } } } } | Select-Object -First 1" > "%TEMP%\ai-creator-lan-ip.txt" 2>nul
if exist "%TEMP%\ai-creator-lan-ip.txt" (
    for /f "usebackq delims=" %%a in ("%TEMP%\ai-creator-lan-ip.txt") do set "LAN_IP=%%a"
    del "%TEMP%\ai-creator-lan-ip.txt" >nul 2>&1
)
if defined LAN_IP (
    echo.
    echo   Mobile - phone on same Wi-Fi:
    echo     Frontend:  http://%LAN_IP%:5173
    echo     Swagger:   http://%LAN_IP%:8000/docs
) else (
    echo.
    echo   Mobile:      LAN IP not detected, run ipconfig to find it.
)

echo.
echo   [tips] Two CMD windows opened for backend and frontend live logs.
echo   [tips] Close a window to stop that service.
echo   [tips] MySQL and Memurai run as Windows services, no manual start needed.
echo   [tips] Mobile: phone and PC must be on the same Wi-Fi; if blocked, allow ports 5173/8000 in Windows Firewall (inbound).
echo   [tips] Wait for the status lines to show HTTP 200 before opening the browser.
echo   [tips] If any status shows HTTP 000, check the matching window title for errors.
echo.
if /i not "%1"=="nopause" pause
