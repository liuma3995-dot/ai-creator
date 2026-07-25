# ai-creator 本地开发 — 调试状态与入口

> 最后更新：2026-07-23（部署首次验证通过）

## 一键启动

| 平台 | 脚本 | 用法 |
|---|---|---|
| Windows 双击 | `scripts\start_dev.bat` | 在文件资源管理器双击运行 |
| Git Bash / WSL | `./scripts/start_dev.sh` | `./scripts/start_dev.sh` |
| 手动（两个终端） | 见下方 "手动启动" | 见下方 |

> ⚠️ Windows 防火墙首次访问时可能弹窗询问是否放行 5173 / 8000 端口，**允许**。

## 当前服务状态

```
┌──────────────┬────────────────────────────────────┬─────────────┬────────┐
│     服务     │                地址                │    状态     │  PID   │
├──────────────┼────────────────────────────────────┼─────────────┼────────┤
│ 前端 Vite    │ http://localhost:5173              │ ✅ HTTP 200 │ 9452   │
│ 后端 uvicorn │ http://localhost:8000              │ ✅ HTTP 200 │ 11196  │
│ 后端 Swagger │ http://localhost:8000/docs         │ ✅ HTTP 200 │ —      │
│ OpenAPI 规格 │ http://localhost:8000/openapi.json │ ✅ HTTP 200 │ —      │
└──────────────┴────────────────────────────────────┴─────────────┴────────┘
```

> PID 每次启动会变，实时查 `netstat -ano | grep ":8000\|:5173" | grep LISTENING`。

## 调试入口

| 用途 | 地址 |
|---|---|
| 电脑浏览器 | http://localhost:5173 |
| 手机 / 局域网 | http://192.168.0.125:5173 |
| Swagger API 文档 | http://localhost:8000/docs |
| OpenAPI JSON 规格 | http://localhost:8000/openapi.json |
| 后端根路径 | http://localhost:8000/ |

## 测试账号

```
用户名: testuser001
密码:   Test@123456
邮箱:   test001@example.com
```

> 该账号在 2026-07-23 部署验证时创建，存于 MySQL `ai_creator.users` 表。

## 手动启动（高级）

### 后端

```bash
cd /d/AIwenan/ai-creator/backend
"/c/Users/Administrator/pyhhhhh/scrapling-venv/Scripts/python.exe" \
  -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd /d/AIwenan/ai-creator/frontend
npm run dev -- --host 0.0.0.0
```

## 热重载

| 类型 | 触发 | 生效范围 |
|---|---|---|
| 后端 `--reload` | 改 `backend/app/**/*.py` 或 `backend/scripts/*.py` | uvicorn 自动重启（约 1-2 秒） |
| 前端 HMR | 改 `frontend/src/**/*` | 浏览器自动热更新，无需手动刷新 |

**不会触发热重载**：`.env` 改动（需重启对应服务）、`vite.config.ts` 改动（需重启 Vite）、`tsconfig.json` 改动（需重启 Vite）。

## 实时日志

| 服务 | 日志位置 | 查看命令 |
|---|---|---|
| 后端（Git Bash 启动） | `/tmp/uvicorn.log` | `tail -f /tmp/uvicorn.log` |
| 前端（Git Bash 启动） | `/tmp/vite.log` | `tail -f /tmp/vite.log` |
| 后端（bat 启动） | 在 "ai-creator-backend" CMD 窗口实时显示 | 直接看新窗口 |
| 前端（bat 启动） | 在 "ai-creator-frontend" CMD 窗口实时显示 | 直接看新窗口 |
| MySQL | Windows 事件查看器 → 应用程序日志 | `eventvwr.msc` |
| Memurai | `C:\Program Files\Redis\Logs\` | `tail -f` 目录下的 log 文件 |

## 停止服务

### 单个服务

找到对应窗口，关掉。或者用 PID 杀：

```powershell
# PowerShell（推荐）
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | ForEach-Object {
  Stop-Process -Id $_.OwningProcess -Force
}
```

### 一键全杀

```powershell
# 保存为 kill_dev.ps1，PowerShell 跑
$ports = @(8000, 5173)
foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $procId = $_.OwningProcess
        Get-Process -Id $procId -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
        # 也杀 multiprocessing-fork 子进程
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$procId" |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
}
```

> ⚠️ 注意：uvicorn 用 `--reload` 时会派生 `multiprocessing-fork` 子进程，只杀主进程端口可能仍被占。上面脚本会连子进程一并清理。

## API 代理说明

前端 `src/api/request.ts` 默认 `baseURL='/api'`，所有请求走 Vite dev server 的 `/api` 代理：

```
浏览器 /api/* 
  → Vite (127.0.0.1:5173) proxy 
  → uvicorn (127.0.0.1:8000) 
  → MySQL/Memurai
```

代理配置在 `frontend/vite.config.ts`：

```typescript
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    '/uploads': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  }
}
```

## 常见调试命令

### 查看 MySQL 数据

```bash
"C:/Program Files/MySQL/MySQL Server 8.0/bin/mysql.exe" -u root -p123456789 ai_creator -e "SELECT id,username,email,role FROM users;"
```

### 测 API（不需要浏览器）

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"newuser","email":"new@example.com","password":"Test@123","confirm_password":"Test@123"}'

# 登录拿 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser001","password":"Test@123456"}' \
  | grep -oE '"access_token":"[^"]+"' | sed 's/"access_token":"//;s/"//')

# 调受保护接口
curl -X GET http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

### 查看 Redis 数据

```bash
"C:/Program Files/Redis/redis-cli.exe" ping
"C:/Program Files/Redis/redis-cli.exe" keys "*"
```

## 相关文档

- 部署 Spec：`D:\AIwenan\docs\superpowers\specs\2026-07-23-ai-creator-local-dev-deployment-design.md`
- 部署 Plan：`D:\AIwenan\docs\superpowers\plans\2026-07-23-ai-creator-local-dev-deployment.md`
- 项目原文档：`docs\DEPLOYMENT.md`、`docs\QUICK_START.md`、`README.md`
