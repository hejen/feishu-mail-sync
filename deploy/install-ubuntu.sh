#!/bin/bash

#===============================================
# 飞书邮件同步助手 - Ubuntu 20.04 部署脚本
#===============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
INSTALL_DIR="/opt/feishu-mail-sync"
REPO_URL="https://github.com/hejen/feishu-mail-sync.git"
DOMAIN=${1:-""}
BACKEND_PORT=8000

# 打印带颜色的消息
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} 1"; }
print_error() { echo -e "${RED}[ERROR]${NC} 1"; }

# 打印标题
print_banner() {
    echo ""
    echo -e "${GREEN}===============================================${NC}"
    echo -e "${GREEN}    飞书邮件同步助手 - Ubuntu 20.04 部署脚本${NC}"
    echo -e "${GREEN}===============================================${NC}"
    echo ""
}

# 检查是否为 root 用户
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 root 权限运行此脚本"
        echo "使用: sudo $0 $@"
        exit 1
    fi
}

# 检查操作系统
check_os() {
    if [ ! -f /etc/os-release ]; then
        print_error "无法检测操作系统"
        exit 1
    fi

    . /etc/os-release

    if [ "$ID" != "ubuntu" ] && [ "$ID" != "debian" ]; then
        print_warning "此脚本专为 Ubuntu/Debian 设计"
        print_warning "当前系统: $PRETTY_NAME"
        read -p "是否继续? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    print_info "操作系统: $PRETTY_NAME"
}

# 更新系统
update_system() {
    print_info "更新系统包..."
    apt update -y
    apt upgrade -y
}

# 安装系统依赖
install_dependencies() {
    print_info "安装系统依赖..."

    # 基础工具
    apt install -y curl wget git build-essential

    # Python 3
    apt install -y python3 python3-pip python3-venv

    # Node.js (使用 NodeSource)
    if ! command -v node &> /dev/null; then
        print_info "安装 Node.js 18.x..."
        curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
        apt install -y nodejs
    fi

    # Nginx
    apt install -y nginx

    # Supervisor
    apt install -y supervisor

    # 验证安装
    print_info "验证安装..."
    print_info "  Python: $(python3 --version)"
    print_info "  Node.js: $(node --version)"
    print_info "  NPM: $(npm --version)"
}

# 安装 Python 依赖
install_python_deps() {
    print_info "安装 Python 依赖..."

    pip3 install fastapi uvicorn sqlalchemy python-multipart python-jose passlib bcrypt
}

# 克隆代码
clone_code() {
    print_info "克隆代码仓库..."

    rm -rf $INSTALL_DIR
    git clone $REPO_URL $INSTALL_DIR
}

# 配置环境变量
setup_environment() {
    print_info "配置环境变量..."

    # 生成随机加密密钥
    ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    cat > $INSTALL_DIR/backend/.env << EOF
# 应用配置
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///./email_sync.db

# 加密密钥（自动生成）
ENCRYPTION_KEY=$ENCRYPTION_KEY

# 同步配置
DEFAULT_SYNC_DAYS=30
MAX_RETRY_COUNT=3
EOF

    print_success "环境变量配置完成"
    print_info "加密密钥已自动生成"
}

# 构建前端
build_frontend() {
    print_info "构建前端..."

    cd $INSTALL_DIR/frontend
    npm install
    npm run build

    if [ ! -d "dist" ]; then
        print_error "前端构建失败"
        exit 1
    fi

    print_success "前端构建完成"
}

# 配置 Supervisor
setup_supervisor() {
    print_info "配置 Supervisor..."

    mkdir -p /var/log/feishu-mail-sync

    cat > /etc/supervisor/conf.d/feishu-mail-sync.conf << EOF
[program:feishu-mail-sync]
directory=$INSTALL_DIR/backend
command=/usr/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT
autostart=true
autorestart=true
startsecs=5
stdout_logfile=/var/log/feishu-mail-sync/stdout.log
stdout_logfile_maxbytes=10MB
stderr_logfile=/var/log/feishu-mail-sync/stderr.log
stderr_logfile_maxbytes=10MB
user=root
EOF

    print_success "Supervisor 配置完成"
}

# 配置 Nginx
setup_nginx() {
    print_info "配置 Nginx..."

    SERVER_NAME=${DOMAIN:-"_"}

    cat > /etc/nginx/sites-available/feishu-mail-sync << EOF
server {
    listen 80;
    server_name $SERVER_NAME;

    access_log /var/log/nginx/feishu-mail-sync.access.log;
    error_log /var/log/nginx/feishu-mail-sync.error.log;

    # 前端静态文件
    location / {
        root $INSTALL_DIR/frontend/dist;
        index index.html;
        try_files \$uri \$uri/ /index.html;

        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
}
EOF

    ln -sf /etc/nginx/sites-available/feishu-mail-sync /etc/nginx/sites-enabled/
    nginx -t

    print_success "Nginx 配置完成"
}

# 启动服务
start_services() {
    print_info "启动服务..."

    systemctl enable supervisor
    systemctl restart supervisor

    sleep 2

    supervisorctl reread
    supervisorctl update
    supervisorctl start feishu-mail-sync

    systemctl enable nginx
    systemctl restart nginx

    print_success "服务启动完成"
}

# 验证部署
verify_deployment() {
    print_info "验证部署..."

    sleep 3

    if curl -s "http://127.0.0.1:$BACKEND_PORT/api/config/providers" > /dev/null; then
        print_success "后端服务正常"
    else
        print_error "后端服务异常"
    fi

    supervisorctl status feishu-mail-sync
}

# 打印完成信息
print_complete() {
    echo ""
    echo -e "${GREEN}===============================================${NC}"
    echo -e "${GREEN}              部署完成!${NC}"
    echo -e "${GREEN}===============================================${NC}"
    echo ""

    if [ -z "$DOMAIN" ]; then
        echo -e "访问地址: ${YELLOW}http://<服务器IP>${NC}"
    else
        echo -e "访问地址: ${YELLOW}http://$DOMAIN${NC}"
    fi

    echo ""
    echo -e "${BLUE}常用命令:${NC}"
    echo "  查看状态:   supervisorctl status feishu-mail-sync"
    echo "  重启服务:   supervisorctl restart feishu-mail-sync"
    echo "  查看日志:   tail -f /var/log/feishu-mail-sync/stdout.log"
    echo ""
}

# 主流程
main() {
    print_banner
    check_root
    check_os
    update_system
    install_dependencies
    install_python_deps
    clone_code
    setup_environment
    build_frontend
    setup_supervisor
    setup_nginx
    start_services
    verify_deployment
    print_complete
}

# 执行
main "$@"
