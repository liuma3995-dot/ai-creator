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
[ -f "$PY" ] || { echo "[错误] 未找到后端虚拟环境: $PY"; exit 1; }
[ -d "$ROOT/frontend/node_modules" ] || { echo "[错误] 前端依赖未安装，请先 npm install"; exit 1; }
[ -f "$ROOT/backend/.env" ] || cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"

# 严格健康检查：后端必须返回 HTTP 200（/health）
# 端口被占用但进程已损坏/旧版本时，杀掉后重新启动
backend_http() {
  curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:8000/health
}

if [ "$(backend_http)" = "200" ]; then
  echo "[1/3] 后端已在 8000 端口正常运行"
else
  for pid in $(netstat -ano | grep ':8000 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
  echo "[1/3] 启动后端 ..."
  cd "$ROOT/backend"
  "$PY" run.py > /tmp/uvicorn.log 2>&1 & UV_PID=$!
  echo "       backend PID=$UV_PID（日志: tail -f /tmp/uvicorn.log）"
fi

# 等待后端就绪（最长 60 秒）。前端必须等后端健康后再启动，
# 否则打开页面时所有接口经 Vite 代理返回 HTTP 500，前端会弹“服务器内部错误”。
echo "[wait] 等待后端就绪 ..."
BACK_WAIT=0
until [ "$(backend_http)" = "200" ]; do
  BACK_WAIT=$((BACK_WAIT + 1))
  if [ "$BACK_WAIT" -ge 30 ]; then
    echo "[错误] 后端 60 秒内未就绪，请检查日志: tail -f /tmp/uvicorn.log"
    exit 1
  fi
  sleep 2
done
echo "[OK] 后端 API 已就绪: http://localhost:8000/health"
echo ""

# 前端健康检查
front_http() {
  curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:5173/
}

if [ "$(front_http)" = "200" ]; then
  echo "[2/3] 前端已在 5173 端口正常运行"
else
  for pid in $(netstat -ano | grep ':5173 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
  echo "[2/3] 启动前端 Vite ..."
  cd "$ROOT/frontend"
  npm run dev -- --host 0.0.0.0 > /tmp/vite.log 2>&1 & FE_PID=$!
  echo "       vite PID=$FE_PID（日志: tail -f /tmp/vite.log）"
fi

# 等待前端就绪（最长 30 秒）
echo "[wait] 等待前端就绪 ..."
FRONT_WAIT=0
until [ "$(front_http)" = "200" ]; do
  FRONT_WAIT=$((FRONT_WAIT + 1))
  if [ "$FRONT_WAIT" -ge 15 ]; then
    echo "[错误] 前端 30 秒内未就绪，请检查日志: tail -f /tmp/vite.log"
    exit 1
  fi
  sleep 2
done
echo "[OK] 前端 Vite 已就绪: http://localhost:5173"
echo ""

# PPTist 健康检查（5174）
pptist_http() {
  curl -s -o /dev/null -w "%{http_code}" --max-time 3 http://localhost:5174/
}

if [ "$(pptist_http)" = "200" ]; then
  echo "[3/3] PPTist 已在 5174 端口正常运行"
else
  for pid in $(netstat -ano | grep ':5174 ' | grep LISTENING | awk '{print $5}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
  echo "[3/3] 启动 PPTist ..."
  cd "$ROOT/frontend/pptist"
  npm run dev > /tmp/pptist.log 2>&1 & PPT_PID=$!
  echo "       pptist PID=$PPT_PID（日志: tail -f /tmp/pptist.log）"
fi

# 等待 PPTist 就绪（最长 60 秒）
echo "[wait] 等待 PPTist 就绪 ..."
PPT_WAIT=0
until [ "$(pptist_http)" = "200" ]; do
  PPT_WAIT=$((PPT_WAIT + 1))
  if [ "$PPT_WAIT" -ge 30 ]; then
    echo "[错误] PPTist 60 秒内未就绪，请检查日志: tail -f /tmp/pptist.log"
    exit 1
  fi
  sleep 2
done
echo "[OK] PPTist 已就绪: http://localhost:5174"
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
printf "  - PPTist Editor  http://localhost:5174          HTTP %s\n" \
  "$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5174/)"

echo ""
echo "=========================================================="
echo "  调试入口"
echo "=========================================================="
echo "  电脑浏览器:  http://localhost:5173"
echo "  Swagger:     http://localhost:8000/docs"
echo "  PPTist:      http://localhost:5174"
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
if [ -n "$UV_PID$FE_PID$PPT_PID" ]; then
  echo "  [tips] 关闭本窗口或运行 kill $UV_PID $FE_PID $PPT_PID 停止服务"
else
  echo "  [tips] 本次服务原本已运行，未由本脚本启动"
fi
echo "  [tips] 上方三个服务确认 HTTP 200 后再打开浏览器"
echo "  [tips] 如果页面仍提示“服务器内部错误”，说明后端窗口可能已崩溃，请检查 /tmp/uvicorn.log 后重新运行本脚本"
echo "  [tips] MySQL/Memurai 是 Windows 服务，无需手动启动"
echo "  [tips] 手机调试：手机与电脑需在同一 Wi-Fi；若无法访问，请在 Windows 防火墙放行 5173/8000/5174 入站端口"
echo ""
