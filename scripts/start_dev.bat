@echo off
chcp 65001 >nul
setlocal

set ROOT=D:\AIwenan\ai-creator
set PY=C:\Users\Administrator\pyhhhhh\scrapling-venv\Scripts\python.exe

echo ==========================================================
echo   ai-creator 本地开发一键启动
echo ==========================================================
echo.

REM 启动后端（新窗口）
echo [1/2] 启动后端 uvicorn（窗口: ai-creator-backend）...
start "ai-creator-backend" cmd /k "cd /d %ROOT%\backend && %PY% -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM 启动前端（新窗口）
echo [2/2] 启动前端 Vite（窗口: ai-creator-frontend）...
start "ai-creator-frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev -- --host 0.0.0.0"

echo.
echo 等待服务启动（约 10 秒）...
timeout /t 12 /nobreak >nul

echo.
echo ==========================================================
echo   服务状态
echo ==========================================================
curl -s -o nul -w "  - 前端 Vite        http://localhost:5173          HTTP %%{http_code}\n" http://localhost:5173/
curl -s -o nul -w "  - 后端 uvicorn    http://localhost:8000          HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - Swagger         http://localhost:8000/docs     HTTP %%{http_code}\n" http://localhost:8000/docs
curl -s -o nul -w "  - OpenAPI         http://localhost:8000/openapi.json  HTTP %%{http_code}\n" http://localhost:8000/openapi.json

echo.
echo ==========================================================
echo   调试入口
echo ==========================================================
echo   电脑浏览器: http://localhost:5173
echo   手机/局域网: http://192.168.0.125:5173
echo   Swagger:    http://localhost:8000/docs
echo   测试账号:    testuser001 / Test@123456

echo.
echo   [tips] 已打开两个新 CMD 窗口，分别跑后端和前端实时日志
echo   [tips] 关掉对应窗口即可停止对应服务
echo   [tips] MySQL/Memurai 是 Windows 服务，无需启动
echo.
pause
