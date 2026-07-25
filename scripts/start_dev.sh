#!/bin/bash
# ai-creator 本地开发一键启动（Git Bash / WSL 用）

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="/c/Users/Administrator/pyhhhhh/scrapling-venv/Scripts/python.exe"

echo "=========================================================="
echo "  ai-creator 本地开发一键启动"
echo "=========================================================="
echo ""

# 启动后端（后台，输出到 log 文件）
echo "[1/2] 启动后端 uvicorn ..."
cd "$ROOT/backend"
"$PY" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
  > /tmp/uvicorn.log 2>&1 &
UV_PID=$!
echo "       uvicorn PID=$UV_PID（日志: tail -f /tmp/uvicorn.log）"

# 启动前端（后台）
echo "[2/2] 启动前端 Vite ..."
cd "$ROOT/frontend"
npm run dev -- --host 0.0.0.0 > /tmp/vite.log 2>&1 &
FE_PID=$!
echo "       vite PID=$FE_PID（日志: tail -f /tmp/vite.log）"

echo ""
echo "等待服务启动（约 10 秒）..."
sleep 12

echo ""
echo "=========================================================="
echo "  服务状态"
echo "=========================================================="
printf "  - 前端 Vite        http://localhost:5173          HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/)"
printf "  - 后端 uvicorn     http://localhost:8000          HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)"
printf "  - Swagger          http://localhost:8000/docs     HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)"

echo ""
echo "=========================================================="
echo "  调试入口"
echo "=========================================================="
echo "  电脑浏览器: http://localhost:5173"
echo "  手机/局域网: http://192.168.0.125:5173"
echo "  Swagger:    http://localhost:8000/docs"
echo "  测试账号:    testuser001 / Test@123456"
echo ""
echo "  [tips] 关掉本窗口或运行 kill $UV_PID $FE_PID 停止服务"
echo "  [tips] MySQL/Memurai 是 Windows 服务，无需启动"
echo ""
