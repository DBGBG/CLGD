#!/bin/bash
# 层冷辊道监控系统部署脚本
# 适用于 Rocky Linux 9

set -e

PROJECT_DIR="/opt/esp-roller-monitor"
BACKUP_DIR="/opt/esp-roller-monitor-backup-$(date +%Y%m%d-%H%M%S)"

echo "========================================"
echo "  ESP层冷辊道监控系统部署脚本"
echo "========================================"

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 用户执行此脚本"
    exit 1
fi

# 安装 Node.js 18+
echo "[1/6] 检查并安装 Node.js..."
if ! command -v node &>/dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" != "18" ]; then
    curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
    dnf install -y nodejs
else
    echo "Node.js 已安装: $(node -v)"
fi

# 安装 Nginx
echo "[2/6] 检查并安装 Nginx..."
if ! command -v nginx &>/dev/null; then
    dnf install -y nginx
    systemctl enable nginx
else
    echo "Nginx 已安装: $(nginx -v 2>&1 | head -1)"
fi

# 备份旧版本
echo "[3/6] 备份旧版本..."
if [ -d "$PROJECT_DIR" ]; then
    mv "$PROJECT_DIR" "$BACKUP_DIR"
    echo "已备份到: $BACKUP_DIR"
fi

# 创建项目目录
echo "[4/6] 创建项目目录..."
mkdir -p "$PROJECT_DIR/backend"
mkdir -p "$PROJECT_DIR/frontend"

# 提示用户手动上传文件
echo ""
echo "========================================"
echo "  请上传以下文件到服务器："
echo "    1. backend.tar.gz -> $PROJECT_DIR/backend.tar.gz"
echo "    2. frontend.tar.gz -> $PROJECT_DIR/frontend.tar.gz"
echo "========================================"
echo ""

read -p "文件上传完成后按 Enter 继续..."

# 解压文件
echo "[5/6] 解压部署文件..."
if [ -f "$PROJECT_DIR/backend.tar.gz" ]; then
    tar -xzf "$PROJECT_DIR/backend.tar.gz" -C "$PROJECT_DIR/backend" --strip-components=1
    echo "后端文件解压完成"
else
    echo "警告: backend.tar.gz 未找到，跳过后端解压"
fi

if [ -f "$PROJECT_DIR/frontend.tar.gz" ]; then
    tar -xzf "$PROJECT_DIR/frontend.tar.gz" -C "$PROJECT_DIR/frontend" --strip-components=1
    echo "前端文件解压完成"
else
    echo "警告: frontend.tar.gz 未找到，跳过前端解压"
fi

# 安装后端依赖
echo "[6/6] 安装后端依赖..."
cd "$PROJECT_DIR/backend"
if [ -f "package.json" ]; then
    npm install --production
fi

# 配置 Nginx
echo "配置 Nginx..."
cat > /etc/nginx/conf.d/esp-roller-monitor.conf << 'EOF'
server {
    listen 80;
    server_name _;

    # 前端静态文件
    location / {
        root /opt/esp-roller-monitor/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://localhost:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 检查 Nginx 配置
nginx -t

# 创建 systemd 服务
cat > /etc/systemd/system/esp-backend.service << EOF
[Unit]
Description=ESP层冷辊道数据API服务
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/esp-roller-monitor/backend
ExecStart=/usr/bin/node server.mjs
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable esp-backend

echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "启动命令:"
echo "  systemctl start esp-backend    # 启动后端"
echo "  systemctl start nginx          # 启动 Nginx"
echo ""
echo "查看日志:"
echo "  journalctl -u esp-backend -f"
echo "  tail -f /var/log/nginx/error.log"
echo ""
echo "访问地址:"
echo "  http://$(hostname -I | awk '{print $1}')"
echo ""
