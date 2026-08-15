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

REM ------------------------------------------------------------------
REM Step 1: Backend - strict health check (HTTP 200 on /health).
REM A stale or broken process on port 8000 is killed and restarted.
REM ------------------------------------------------------------------
set "AIC_BACK_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 3 http://localhost:8000/health') do set "AIC_BACK_HTTP=%%c"
if "%AIC_BACK_HTTP%"=="200" (
    echo [1/3] Backend already healthy on port 8000.
) else (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
    echo [1/3] Starting backend window ai-creator-backend...
    start "ai-creator-backend" cmd /k "cd /d %ROOT%\backend && %PY% run.py"
)

REM Wait until the backend /health returns HTTP 200 (max ~60s).
REM The frontend is intentionally NOT started before the backend is ready,
REM otherwise every API call through the Vite proxy returns HTTP 500 and
REM the app shows "server internal error" when the page is opened early.
echo [wait] Waiting for backend API on port 8000 ...
set "AIC_BACK_WAIT=0"
:wait_backend
set "AIC_BACK_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 2 http://localhost:8000/health') do set "AIC_BACK_HTTP=%%c"
if "%AIC_BACK_HTTP%"=="200" goto backend_ready
set /a AIC_BACK_WAIT+=1
if %AIC_BACK_WAIT% geq 30 (
    echo [ERROR] Backend did not become healthy within 60s.
    echo         Check the ai-creator-backend window for errors.
    echo         After fixing, close that window and rerun this script.
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_backend
:backend_ready
echo [OK] Backend API healthy on http://localhost:8000/health
echo.

REM ------------------------------------------------------------------
REM Step 2: Frontend - strict health check (HTTP 200 on the root page).
REM ------------------------------------------------------------------
set "AIC_FRONT_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 3 http://localhost:5173/') do set "AIC_FRONT_HTTP=%%c"
if "%AIC_FRONT_HTTP%"=="200" (
    echo [2/3] Frontend already responding on port 5173.
) else (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":5173 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
    echo [2/3] Starting frontend Vite window ai-creator-frontend...
    start "ai-creator-frontend" cmd /k "cd /d %ROOT%\frontend && npm.cmd run dev -- --host 0.0.0.0"
)

REM Wait until the frontend responds with HTTP 200 (max ~30s).
echo [wait] Waiting for frontend Vite on port 5173 ...
set "AIC_FRONT_WAIT=0"
:wait_front
set "AIC_FRONT_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 2 http://localhost:5173/') do set "AIC_FRONT_HTTP=%%c"
if "%AIC_FRONT_HTTP%"=="200" goto front_ready
set /a AIC_FRONT_WAIT+=1
if %AIC_FRONT_WAIT% geq 15 (
    echo [ERROR] Frontend did not become ready within 30s.
    echo         Check the ai-creator-frontend window for errors.
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_front
:front_ready
echo [OK] Frontend Vite ready on http://localhost:5173
echo.

REM ------------------------------------------------------------------
REM Step 3: PPTist editor - strict health check (HTTP 200 on root page).
REM ------------------------------------------------------------------
set "AIC_PPTIST_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 3 http://localhost:5174/') do set "AIC_PPTIST_HTTP=%%c"
if "%AIC_PPTIST_HTTP%"=="200" (
    echo [3/3] PPTist already responding on port 5174.
) else (
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":5174 " ^| findstr "LISTENING"') do taskkill /F /PID %%p >nul 2>&1
    echo [3/3] Starting PPTist window ai-creator-pptist...
    start "ai-creator-pptist" cmd /k "cd /d %ROOT%\frontend\pptist && npm.cmd run dev"
)

REM Wait until the PPTist responds with HTTP 200 (max ~60s).
echo [wait] Waiting for PPTist on port 5174 ...
set "AIC_PPTIST_WAIT=0"
:wait_pptist
set "AIC_PPTIST_HTTP="
for /f %%c in ('curl -s -o nul -w "%%{http_code}" --max-time 2 http://localhost:5174/') do set "AIC_PPTIST_HTTP=%%c"
if "%AIC_PPTIST_HTTP%"=="200" goto pptist_ready
set /a AIC_PPTIST_WAIT+=1
if %AIC_PPTIST_WAIT% geq 30 (
    echo [ERROR] PPTist did not become ready within 60s.
    echo         Check the ai-creator-pptist window for errors.
    pause
    exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_pptist
:pptist_ready
echo [OK] PPTist ready on http://localhost:5174
echo.

echo ==========================================================
echo   Service status
echo ==========================================================
curl -s -o nul -w "  - Frontend Vite   http://localhost:5173          HTTP %%{http_code}\n" http://localhost:5173/
curl -s -o nul -w "  - Backend API     http://localhost:8000          HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - Swagger         http://localhost:8000/docs     HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - OpenAPI         http://localhost:8000/openapi.json  HTTP %%{http_code}\n" http://localhost:8000/openapi.json
curl -s -o nul -w "  - PPTist Editor   http://localhost:5174          HTTP %%{http_code}\n" http://localhost:5174/

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
echo   [tips] Both services are confirmed ready above; open the browser now.
echo   [tips] Three CMD windows opened for backend, frontend and PPTist live logs.
echo   [tips] Close a window to stop that service.
echo   [tips] If the page still shows "server internal error", the backend
echo          window may have crashed - check it, then rerun this script.
echo   [tips] MySQL and Memurai run as Windows services, no manual start needed.
echo   [tips] Mobile: phone and PC must be on the same Wi-Fi; if blocked, allow ports 5173/8000 in Windows Firewall (inbound).
echo.
if /i not "%1"=="nopause" pause
