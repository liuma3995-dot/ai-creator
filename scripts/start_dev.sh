#!/bin/bash
# ai-creator 本地开发一键启动（Git Bash / WSL 用户）

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/backend/venv/Scripts/python.exe"

echo "=========================================================="
echo "  ai-creator 本地开发一键启动"
echo "=========================================================="
echo ""

# 前置检查：MySQL / Memurai 服务
sc query MySQL80 | grep -q RUNNING || { echo "[错误] MySQL 服务未运行"; exit 1; }
sc query Memurai | grep -q RUNNING || { echo "[错误] Memurai(Redis) 服务未运行"; exit 1; }

# 依赖检查
[ -f "$PY" ] || { echo "[错误] 未找到后端虚拟环境 $PY"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "[错误] 前端依赖未安装，请先 npm install"; exit 1; }
[ -f "$ROOT/backend/.env" ] || cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"

UV_PID=""
FE_PID=""

# 启动后端（后台，日志到 /tmp/uvicorn.log；先健康检查，端口占用但不响应则清理后重启）
if curl -s -o /dev/null --max-time 3 http://localhost:8000/docs; then
  echo "[1/2] 已跳过：后端已在 8000 端口正常运行"
else
  for pid in $(netstat -ano | grep ':8000 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
  echo "[1/2] 启动后端 ..."
  cd "$ROOT/backend"
  "$PY" run.py > /tmp/uvicorn.log 2>&1 &
  UV_PID=$!
  echo "       backend PID=$UV_PID（日志: tail -f /tmp/uvicorn.log）"
fi

# 启动前端（后台，日志到 /tmp/vite.log）
if curl -s -o /dev/null --max-time 3 http://localhost:5173/; then
  echo "[2/2] 已跳过：前端已在 5173 端口正常运行"
else
  for pid in $(netstat -ano | grep ':5173 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
  echo "[2/2] 启动前端 Vite ..."
  cd "$ROOT/frontend"
  npm run dev -- --host 0.0.0.0 > /tmp/vite.log 2>&1 &
  FE_PID=$!
  echo "       vite PID=$FE_PID（日志: tail -f /tmp/vite.log）"
fi

echo ""
echo "等待服务启动（约 15 秒）..."
sleep 15

echo ""
echo "=========================================================="
echo "  服务状态"
echo "=========================================================="
printf "  - 前端 Vite      http://localhost:5173          HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/)"
printf "  - 后端 API       http://localhost:8000          HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)"
printf "  - Swagger        http://localhost:8000/docs     HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)"

echo ""
echo "=========================================================="
echo "  调试入口"
echo "=========================================================="
echo "  电脑浏览器:  http://localhost:5173"
echo "  Swagger:     http://localhost:8000/docs"
echo "  测试账号:    admin / admin123456"

# 检测局域网 IP（手机调试用：取有默认网关的活动网卡 IPv4）
LAN_IP=$(powershell.exe -NoProfile -Command '[System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() | Where-Object { $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up -and $_.NetworkInterfaceType -ne [System.Net.NetworkInformation.NetworkInterfaceType]::Loopback -and $_.NetworkInterfaceType -ne [System.Net.NetworkInformation.NetworkInterfaceType]::Tunnel } | ForEach-Object { $ip=$_.GetIPProperties(); if ($ip.GatewayAddresses.Count -gt 0) { foreach ($u in $ip.UnicastAddresses) { if ($u.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) { $b=$u.Address.GetAddressBytes(); if ($b[0] -ne 127 -and $b[0] -ne 169) { $u.Address.ToString() } } } } } | Select-Object -First 1' 2>/dev/null | tr -d '\r')
if [ -z "$LAN_IP" ]; then
  LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

if [ -n "$LAN_IP" ]; then
  echo ""
  echo "  手机调试（同一 Wi-Fi）:"
  echo "    前端:      http://$LAN_IP:5173"
  echo "    Swagger:   http://$LAN_IP:8000/docs"
else
  echo ""
  echo "  手机调试:   未检测到局域网 IP，请用 ipconfig 查看"
fi

echo ""
if [ -n "$UV_PID$FE_PID" ]; then
  echo "  [tips] 关闭本窗口或运行 kill $UV_PID $FE_PID 停止服务"
else
  echo "  [tips] 本次服务原本已运行，未由本脚本启动"
fi
echo "  [tips] MySQL/Memurai 是 Windows 服务，无需手动启动"
echo "  [tips] 手机调试：手机与电脑需在同一 Wi-Fi；若无法访问，请在 Windows 防火墙放行 5173/8000 入站端口"
echo "  [tips] 等上面的服务状态显示 HTTP 200 后再打开浏览器"
echo ""
