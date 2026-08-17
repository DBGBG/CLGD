#!/bin/bash
# ESP层冷辊道监控系统 - 离线一键安装脚本
# 适用于无外网的 Rocky Linux 服务器

set -e

PROJECT_DIR="/opt/esp-roller-monitor"
NODE_DIR="/usr/local/node-v18.20.4-linux-x64"
BACKUP_DIR="/opt/esp-roller-monitor-backup-$(date +%Y%m%d-%H%M%S)"

echo "========================================"
echo "  ESP层冷辊道监控系统 - 离线安装"
echo "========================================"

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用 root 用户执行此脚本"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "[1/6] 安装 Node.js..."
if [ ! -d "$NODE_DIR" ]; then
    if [ -f "$SCRIPT_DIR/node/node-v18.20.4-linux-x64.tar.xz" ]; then
        tar -xf "$SCRIPT_DIR/node/node-v18.20.4-linux-x64.tar.xz" -C /usr/local/
        echo "Node.js 解压完成"
    else
        echo "错误: Node.js 包未找到"
        exit 1
    fi
else
    echo "Node.js 已存在，跳过"
fi

# 创建软链接
ln -sf "$NODE_DIR/bin/node" /usr/local/bin/node
ln -sf "$NODE_DIR/bin/npm" /usr/local/bin/npm
ln -sf "$NODE_DIR/bin/npx" /usr/local/bin/npx

# 验证 Node.js
echo "Node.js 版本: $(node -v)"
echo "npm 版本: $(npm -v)"

echo ""
echo "[2/6] 备份旧版本..."
if [ -d "$PROJECT_DIR" ]; then
    mv "$PROJECT_DIR" "$BACKUP_DIR"
    echo "已备份到: $BACKUP_DIR"
fi

# 创建项目目录
echo ""
echo "[3/6] 创建项目目录..."
mkdir -p "$PROJECT_DIR/backend"
mkdir -p "$PROJECT_DIR/frontend"

echo ""
echo "[4/6] 复制文件..."
# 复制后端
cp -r "$SCRIPT_DIR/backend/"* "$PROJECT_DIR/backend/"
echo "后端文件复制完成"

# 复制前端
cp -r "$SCRIPT_DIR/frontend/dist/"* "$PROJECT_DIR/frontend/"
echo "前端文件复制完成"

# 复制数据文件
if [ -f "$SCRIPT_DIR/backend/meter_ledger.csv" ]; then
    cp "$SCRIPT_DIR/backend/meter_ledger.csv" "$PROJECT_DIR/backend/"
fi

echo ""
echo "[5/6] 安装后端依赖..."
# 检查 node_modules 是否存在
if [ ! -d "$PROJECT_DIR/backend/node_modules" ]; then
    echo "警告: node_modules 未找到，尝试从部署包复制"
    if [ -d "$SCRIPT_DIR/backend/node_modules" ]; then
        cp -r "$SCRIPT_DIR/backend/node_modules" "$PROJECT_DIR/backend/"
        echo "依赖已复制"
    else
        echo "错误: 未找到 node_modules，请确保预安装了依赖"
        exit 1
    fi
else
    echo "依赖已存在，跳过"
fi

echo ""
echo "[6/6] 配置服务..."

# 创建 systemd 服务
cat > /etc/systemd/system/esp-backend.service << EOF
[Unit]
Description=ESP层冷辊道数据API服务
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/backend
ExecStart=/usr/local/bin/node server.mjs
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production
Environment=PATH=/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF

# 检查是否有 Nginx
if command -v nginx &>/dev/null; then
    echo "配置 Nginx..."
    cat > /etc/nginx/conf.d/esp-roller-monitor.conf << EOF
server {
    listen 80;
    server_name _;

    location / {
        root $PROJECT_DIR/frontend;
        index index.html;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8080/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    nginx -t && systemctl reload nginx
    echo "Nginx 配置完成"
else
    echo "警告: Nginx 未安装，跳过 Nginx 配置"
    echo "提示: 可以直接访问 http://$(hostname -I | awk '{print $1}'):8080 访问后端 API"
fi

# 启动服务
systemctl daemon-reload
systemctl enable esp-backend
systemctl start esp-backend

echo ""
echo "========================================"
echo "  离线部署完成！"
echo "========================================"
echo ""
echo "访问地址:"
echo "  前端: http://$(hostname -I | awk '{print $1}')"
echo "  API: http://$(hostname -I | awk '{print $1}'):8080/api"
echo ""
echo "常用命令:"
echo "  systemctl start esp-backend    # 启动后端"
echo "  systemctl stop esp-backend     # 停止后端"
echo "  systemctl status esp-backend   # 查看状态"
echo "  journalctl -u esp-backend -f  # 查看日志"
echo ""
