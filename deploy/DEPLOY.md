# ESP 层冷辊道监控系统部署指南

## 服务器信息
- **IP**: 10.51.190.71
- **系统**: Rocky Linux 9
- **用户名**: root
- **密码**: rg.xxxtc.f37

---

## 部署步骤

### 1. 连接服务器

使用 SSH 客户端（如 PuTTY、MobaXterm、XShell）连接：
```
ssh root@10.51.190.71
密码: rg.xxxtc.f37
```

### 2. 安装 Node.js 18

```bash
# 安装 Node.js 18
curl -fsSL https://rpm.nodesource.com/setup_18.x | bash -
dnf install -y nodejs

# 验证
node -v  # v18.x.x
npm -v   # 9.x.x
```

### 3. 安装 Nginx

```bash
dnf install -y nginx
systemctl enable nginx
systemctl start nginx
```

### 4. 创建项目目录

```bash
mkdir -p /opt/esp-roller-monitor/backend
mkdir -p /opt/esp-roller-monitor/frontend
```

### 5. 上传文件

将以下文件上传到服务器对应目录：

| 本地文件 | 服务器路径 |
|---------|-----------|
| `deploy/backend/server.mjs` | `/opt/esp-roller-monitor/backend/server.mjs` |
| `deploy/backend/package.json` | `/opt/esp-roller-monitor/backend/package.json` |
| `deploy/backend/meter_ledger.csv` | `/opt/esp-roller-monitor/backend/meter_ledger.csv` |
| `deploy/frontend/dist/` 全部文件 | `/opt/esp-roller-monitor/frontend/dist/` |

**上传方式**（任选一种）：
- **SCP**: `scp -r deploy/* root@10.51.190.71:/opt/esp-roller-monitor/`
- **SFTP**: 使用 FileZilla、WinSCP 等工具上传
- **直接复制**: 在服务器上直接下载

### 6. 安装后端依赖

```bash
cd /opt/esp-roller-monitor/backend
npm install --production
```

### 7. 配置 Nginx

创建 Nginx 配置文件：

```bash
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
```

检查配置并重启：
```bash
nginx -t
systemctl reload nginx
```

### 8. 创建后端服务

```bash
cat > /etc/systemd/system/esp-backend.service << 'EOF'
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
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable esp-backend
systemctl start esp-backend
```

### 9. 验证部署

```bash
# 检查后端状态
systemctl status esp-backend

# 检查后端日志
journalctl -u esp-backend -f

# 检查 Nginx 状态
systemctl status nginx

# 测试 API
curl http://localhost:8080/api/rollers
```

### 10. 访问系统

在浏览器中打开：
```
http://10.51.190.71
```

---

## 常用命令

```bash
# 启动后端
systemctl start esp-backend

# 停止后端
systemctl stop esp-backend

# 重启后端
systemctl restart esp-backend

# 查看后端日志
journalctl -u esp-backend -f

# 重启 Nginx
systemctl reload nginx

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

---

## 文件清单

```
deploy/
├── backend/
│   ├── server.mjs        # 后端服务主文件
│   ├── package.json      # 后端依赖配置
│   └── meter_ledger.csv  # 辊道数据
├── frontend/
│   └── dist/             # 前端构建文件
│       ├── index.html
│       ├── favicon.ico
│       └── assets/       # JS/CSS 资源文件
└── deploy.md             # 本指南
```