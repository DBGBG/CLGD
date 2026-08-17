#!/bin/bash
# ESP层冷辊道监控系统 - 极简一键部署
# 适用于有外网的 Rocky Linux 9

set -e

PROJECT_DIR="/opt/esp-roller-monitor"

echo "========================================"
echo "  ESP层冷辊道监控系统 - 一键部署"
echo "========================================"

# 1. 安装 Node.js 18
echo "[1/5] 安装 Node.js..."
if ! command -v node &>/dev/null; then
  curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
  dnf install -y nodejs
fi
echo "Node.js: $(node -v)"

# 2. 安装 Nginx
echo "[2/5] 安装 Nginx..."
if ! command -v nginx &>/dev/null; then
  dnf install -y nginx
  systemctl enable nginx
  systemctl start nginx
fi

# 3. 创建目录
echo "[3/5] 创建项目目录..."
mkdir -p $PROJECT_DIR/backend
mkdir -p $PROJECT_DIR/frontend

echo ""
echo "========================================"
echo "  请手动上传以下文件到服务器："
echo "========================================"
echo ""
echo "  1. backend/server.mjs     -> $PROJECT_DIR/backend/"
echo "  2. backend/meter_ledger.csv -> $PROJECT_DIR/backend/"
echo "  3. frontend/dist/*        -> $PROJECT_DIR/frontend/"
echo ""
echo "  上传完成后按 Enter 继续..."
read -r

# 4. 安装依赖
echo "[4/5] 安装后端依赖..."
cd $PROJECT_DIR/backend
cat > package.json << 'EOF'
{
  "name": "esp-roller-backend",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.18.2"
  }
}
EOF
npm install --production

# 5. 配置 Nginx
echo "[5/5] 配置 Nginx..."
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
    }
}
EOF
nginx -t && systemctl reload nginx

# 6. 创建 systemd 服务
cat > /etc/systemd/system/esp-backend.service << EOF
[Unit]
Description=ESP层冷辊道数据API服务
After=network.target
[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/backend
ExecStart=/usr/bin/node server.mjs
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable esp-backend
systemctl start esp-backend

echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "访问地址: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "查看状态: systemctl status esp-backend"
echo "查看日志: journalctl -u esp-backend -f"
