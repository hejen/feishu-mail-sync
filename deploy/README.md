# 飞书邮件同步 - 火山云部署指南

## 服务器要求

- 操作系统: CentOS 7+ / Ubuntu 18.04+
- 内存: 最低 1GB
- 存储: 最低 10GB
- 网络: 开放 80, 443 端口

## 1. 服务器初始化

```bash
# 更新系统
yum update -y  # CentOS
# apt update && apt upgrade -y  # Ubuntu

# 安装依赖
yum install -y python3 python3-pip nodejs nginx git supervisor
# apt install -y python3 python3-pip nodejs nginx git supervisor  # Ubuntu

# 安装 Python 依赖
pip3 install fastapi uvicorn sqlalchemy python-multipart python-jose passlib bcrypt
```

## 2. 部署代码

```bash
# 创建目录
mkdir -p /opt/feishu-mail-sync
cd /opt/feishu-mail-sync

# 从 GitHub 拉取代码
git clone https://github.com/hejen/feishu-mail-sync.git .

# 或者从本地上传
# scp -r ./feishu-mail-sync/* root@your-server-ip:/opt/feishu-mail-sync/
```

## 3. 配置环境变量

```bash
# 创建生产环境配置
cat > /opt/feishu-mail-sync/backend/.env << 'EOF'
# 应用配置
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///./email_sync.db

# 加密密钥（必须修改为随机32字节字符串）
ENCRYPTION_KEY=请修改为随机32字节字符串!!

# 同步配置
DEFAULT_SYNC_DAYS=30
MAX_RETRY_COUNT=3
EOF

# 生成随机密钥
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# 将生成的密钥替换到 ENCRYPTION_KEY
```

## 4. 构建前端

```bash
cd /opt/feishu-mail-sync/frontend
npm install
npm run build
```

## 5. 配置 Supervisor (进程管理)

```bash
# 创建 supervisor 配置
cat > /etc/supervisord.d/feishu-mail-sync.ini << 'EOF'
[program:feishu-mail-sync]
directory=/opt/feishu-mail-sync/backend
command=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
autostart=true
autorestart=true
startsecs=10
stdout_logfile=/var/log/feishu-mail-sync/stdout.log
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=10
stderr_logfile=/var/log/feishu-mail-sync/stderr.log
stderr_logfile_maxbytes=1MB
user=root
EOF

# 创建日志目录
mkdir -p /var/log/feishu-mail-sync

# 启动服务
supervisorctl reread
supervisorctl update
supervisorctl start feishu-mail-sync
```

## 6. 配置 Nginx

```bash
# 创建 Nginx 配置
cat > /etc/nginx/conf.d/feishu-mail-sync.conf << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 修改为您的域名或服务器IP

    # 前端静态文件
    location / {
        root /opt/feishu-mail-sync/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 飞书插件需要的服务器配置
    location ~ ^/(api|socket) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# 测试配置
nginx -t

# 重载 Nginx
systemctl reload nginx
```

## 7. 配置防火墙

```bash
# CentOS
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload

# Ubuntu
ufw allow 80
ufw allow 443
```

## 8. 配置 SSL (可选但推荐)

```bash
# 安装 certbot
yum install -y certbot python3-certbot-nginx
# apt install -y certbot python3-certbot-nginx  # Ubuntu

# 获取证书
certbot --nginx -d your-domain.com

# 自动续期
crontab -e
# 添加: 0 0 * * * /usr/bin/certbot renew --quiet
```

## 9. 验证部署

```bash
# 检查后端服务
curl http://localhost:8000/api/config/providers

# 检查前端
curl http://localhost/

# 查看日志
tail -f /var/log/feishu-mail-sync/stdout.log
```

## 常用命令

```bash
# 重启后端服务
supervisorctl restart feishu-mail-sync

# 查看服务状态
supervisorctl status feishu-mail-sync

# 重新加载 Nginx
systemctl reload nginx

# 更新代码
cd /opt/feishu-mail-sync
git pull
supervisorctl restart feishu-mail-sync
```

## 故障排查

1. **后端无法启动**: 检查 `.env` 配置和 Python 依赖
2. **前端无法访问**: 检查 Nginx 配置和 dist 目录
3. **API 500 错误**: 查看 `/var/log/feishu-mail-sync/stderr.log`
4. **飞书插件无法连接**: 检查防火墙和 CORS 配置
