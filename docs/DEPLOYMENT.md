# AI创作者平台部署指南

## 目录
- [环境要求](#环境要求)
- [本地开发部署](#本地开发部署)
- [Docker部署](#docker部署)
- [生产环境部署](#生产环境部署)
- [常见问题](#常见问题)

## 环境要求

### 基础环境
- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 7+
- Docker & Docker Compose (可选)

### 系统要求
- 操作系统：Linux/macOS/Windows
- 内存：最低4GB，推荐8GB+
- 磁盘：最低20GB可用空间
- 网络：需要访问外部AI服务API

## 本地开发部署

### 1. 克隆项目
```bash
git clone https://github.com/your-repo/ai-creator.git
cd ai-creator
```

### 2. 配置环境变量
```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑.env文件，填写实际配置
vim .env
```

### 3. 后端部署

#### 3.1 安装依赖
```bash
cd backend
pip install -r requirements.txt
```

#### 3.2 初始化数据库
```bash
# 确保MySQL已启动
# 创建数据库
mysql -u root -p -e "CREATE DATABASE ai_creator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 运行初始化脚本
python scripts/init_db.py
```

#### 3.3 启动后端服务
```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或使用脚本
python -m app.main
```

#### 3.4 启动Celery Worker（可选）
```bash
# 新开一个终端
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

### 4. 前端部署

#### 4.1 安装依赖
```bash
cd frontend
npm install
```

#### 4.2 配置API地址
编辑 `frontend/src/api/request.ts`，确保baseURL指向后端地址：
```typescript
const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

#### 4.3 启动开发服务器
```bash
npm run dev
```

访问 http://localhost:5173 查看应用

### 5. 验证部署
- 后端API文档：http://localhost:8000/docs
- 前端应用：http://localhost:5173
- 测试注册登录功能
- 测试AI写作功能

> 提示：也可以直接使用一键启动脚本（自动拉起后端/前端/PPTist 并做健康检查）：
> - Windows：`scripts/start_dev.bat`
> - Git Bash / WSL：`scripts/start_dev.sh`

## Docker部署

### 1. 准备工作
```bash
# 确保已安装Docker和Docker Compose
docker --version
docker-compose --version

# 配置环境变量
cp .env.example .env
vim .env
```

### 2. 构建并启动服务
```bash
# 构建镜像
docker-compose build

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 初始化数据库
```bash
# 进入后端容器
docker-compose exec backend bash

# 运行初始化脚本
python scripts/init_db.py

# 退出容器
exit
```

### 4. 访问应用
- 前端（Nginx 容器）：http://localhost:8080
- 后端 API：http://localhost:8000（仅本机/内网可访问，已绑定 127.0.0.1，公网流量统一走 Nginx）
- API文档：http://localhost:8000/docs（开发环境可用；生产模式默认关闭）

### 5. 常用Docker命令
```bash
# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker-compose exec [service_name] bash
```

## 生产环境部署

### 1. 服务器准备

#### 1.1 系统配置
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y git curl wget vim

# 安装Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

#### 1.2 配置防火墙
```bash
# 开放必要端口
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### 2. 部署应用

#### 2.1 克隆代码
```bash
cd /opt
sudo git clone https://github.com/your-repo/ai-creator.git
cd ai-creator
```

#### 2.2 配置环境
```bash
# 复制并编辑环境变量
sudo cp .env.example .env
sudo vim .env

# 重要：修改以下配置
# - SECRET_KEY: 生成强密码
# - JWT_SECRET_KEY: 生成强密码
# - ADMIN_SECRET_KEY: 管理端令牌独立签名密钥（建议单独设置）
# - PAYMENT_CALLBACK_SECRET / OAUTH_ENCRYPTION_KEY: 支付回调与 OAuth 加密密钥
# - ADMIN_IP_WHITELIST: 管理接口 IP 白名单（VPN 网段）
# - ADMIN_INIT_PASSWORD: 管理员初始密码（initdb 使用）
# - ENABLE_API_DOCS: 生产默认关闭 API 文档，需要时设为 true
# - DEBUG: 生产必须为 False
# - 数据库密码
# - Redis密码
# - AI服务API密钥
# - 平台发布配置
```

#### 2.3 安全加固配置（生产必做）

以下配置在对外开放前必须完成，否则管理端存在被攻击风险：

1. **生产密钥**：`DEBUG=False` 时，以下密钥若仍为默认值/空值，后端会拒绝启动：
   - `SECRET_KEY`、`PAYMENT_CALLBACK_SECRET`、`OAUTH_ENCRYPTION_KEY` 必须改为强随机值；
   - 建议单独设置 `ADMIN_SECRET_KEY`（管理端令牌签名密钥，与用户端隔离）。
2. **管理员初始密码**：`initdb` 创建管理员时读取 `ADMIN_INIT_PASSWORD`；留空则生成随机强密码仅打印一次，请立即保存并登录修改。
3. **管理接口 IP 白名单**：
   - 部署 VPN（推荐 Tailscale / WireGuard），编辑 `frontend/admin_ip_whitelist.conf` 放行 VPN 网段（如 `allow 10.0.0.0/8;`），默认全部拒绝；
   - 覆盖范围包括 `/api/v1/admin/*` 与 `/api/v1/auth/admin/*`（管理登录/刷新端点同样受白名单保护）；
   - 后端端口已改为仅绑定 `127.0.0.1`，公网流量统一走 Nginx；
   - 应用层兜底：`ADMIN_IP_WHITELIST` 环境变量填写白名单（如 `["10.0.0.0/8"]`），留空表示不限制。
4. **登录限流与锁定**：登录接口已内置 IP 限流与连续失败锁定（默认 5 次失败锁定 15 分钟），管理员登录阈值更严格（每分钟 5 次）。
5. **HTTPS**：管理端与用户端都必须走 TLS，避免令牌明文传输。
6. **账号处置规范**：用户管理仅提供“停用/启用”能力，删除功能已从前端下线；后端归档接口仅软删且需二次确认，禁止任何硬删路径。垃圾/违规账号一律停用，用户申请注销时做匿名化（清空邮箱、手机、昵称等个人标识），业务数据保留。
7. **管理端入口**：公网登录页 `/login` 仅提供用户登录；管理员通过独立隐藏入口 `https://<你的域名>/admin-login` 登录（需在 VPN/白名单网段内）。该入口不在任何导航中出现，建议管理员保存书签。
8. **API 文档**：生产模式（`DEBUG=False`）默认关闭 `/docs`、`/redoc`、`/openapi.json`；如确需开放，设置 `ENABLE_API_DOCS=true` 并在 Nginx 对文档路径单独加白名单。

#### 2.4 配置SSL证书（推荐）
```bash
# 使用Let's Encrypt
sudo apt install -y certbot

# 获取证书
sudo certbot certonly --standalone -d your-domain.com

# 证书路径
# /etc/letsencrypt/live/your-domain.com/fullchain.pem
# /etc/letsencrypt/live/your-domain.com/privkey.pem
```

#### 2.5 配置Nginx（如果使用SSL）
编辑 `frontend/nginx.conf`：
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    # ... 其他配置
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

#### 2.6 启动服务
```bash
# 构建并启动
sudo docker-compose -f docker-compose.yml up -d --build

# 初始化数据库
sudo docker-compose exec backend python scripts/init_db.py

# 查看日志
sudo docker-compose logs -f
```

### 3. 配置自动备份

#### 3.1 数据库备份脚本
创建 `scripts/backup.sh`：
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
MYSQL_CONTAINER="ai-creator-mysql"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库（密码通过环境变量 MYSQL_ROOT_PASSWORD 传入，勿写入脚本）
docker exec $MYSQL_CONTAINER mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" \
  --single-transaction --routines --triggers ai_creator \
  | gzip > "$BACKUP_DIR/ai_creator_$DATE.sql.gz"

# 清理 30 天前的备份
find "$BACKUP_DIR" -name "ai_creator_*.sql.gz" -mtime +30 -delete

echo "备份完成: $BACKUP_DIR/ai_creator_$DATE.sql.gz"
```

建议配合 cron 每日执行（`crontab -e`）：
```bash
0 3 * * * MYSQL_ROOT_PASSWORD=你的密码 /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```
