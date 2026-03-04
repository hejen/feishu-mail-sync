#!/bin/bash

# 飞书邮件同步 - 一键部署脚本
# 使用方法: bash install.sh

set -e

echo "==================================="
echo "  飞书邮件同步 - 火山云部署脚本"
echo "==================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置变量
INSTALL_DIR="/opt/feishu-mail-sync"
DOMAIN=${1:-""}

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行此脚本${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/8] 安装系统依赖...${NC}"
if command -v yum &> /dev/null; then
    yum install -y python3 python3-pip nodejs nginx git supervisor
elif command -v apt &> /dev/null; then
    apt update
    apt install -y python3 python3-pip nodejs nginx git supervisor
else
    echo -e "${RED}不支持的操作系统${NC}"
    exit 1
fi

echo -e "${YELLOW}[2/8] 安装 Python 依赖...${NC}"
pip3 install fastapi uvicorn sqlalchemy python-multipart python-jose passlib bcrypt

echo -e "${YELLOW}[3/8] 创建目录结构...${NC}"
mkdir -p $INSTALL_DIR
mkdir -p /var/log/feishu-mail-sync

echo -e "${YELLOW}[4/8] 配置环境变量...${NC}"
# 生成随机密钥
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

cat > $INSTALL_DIR/backend/.env << EOF
# 应用配置
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///./email_sync.db

# 加密密钥
ENCRYPTION_KEY=$ENCRYPTION_KEY

# 同步配置
DEFAULT_SYNC_DAYS=30
MAX_RETRY_COUNT=3
EOF

echo -e "${GREEN}已生成加密密钥: $ENCRYPTION_KEY${NC}"

echo -e "${YELLOW}[5/8] 构建前端...${NC}"
cd $INSTALL_DIR/frontend
npm install
npm run build

echo -e "${YELLOW}[6/8] 配置 Supervisor...${NC}"
cat > /etc/supervisord.d/feishu-mail-sync.ini << EOF
[program:feishu-mail-sync]
directory=$INSTALL_DIR/backend
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

echo -e "${YELLOW}[7/8] 配置 Nginx...${NC}"
SERVER_NAME=${DOMAIN:-"_"}

cat > /etc/nginx/conf.d/feishu-mail-sync.conf << EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    location / {
        root $INSTALL_DIR/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location ~ ^/(api|socket) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

nginx -t

echo -e "${YELLOW}[8/8] 启动服务...${NC}"
# 启动 Supervisor
systemctl enable supervisord
systemctl start supervisord

# 启动 Nginx
systemctl enable nginx
systemctl start nginx

# 重载配置
supervisorctl reread
supervisorctl update
supervisorctl start feishu-mail-sync
systemctl reload nginx

echo ""
echo -e "${GREEN}==================================="
echo "  部署完成!"
echo "===================================${NC}"
echo ""
echo "访问地址: http://${DOMAIN:-your-server-ip}"
echo ""
echo "常用命令:"
echo "  查看状态: supervisorctl status feishu-mail-sync"
echo "  重启服务: supervisorctl restart feishu-mail-sync"
echo "  查看日志: tail -f /var/log/feishu-mail-sync/stdout.log"
echo ""
