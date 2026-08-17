# ESP 层冷辊道监控系统 - 离线部署指南

> **适用场景**: 目标服务器无外网访问权限，所有依赖需在本地准备后一次性上传。

---

## 服务器信息

- **IP**: 10.51.190.71
- **系统**: Rocky Linux 9
- **用户名**: root
- **密码**: rg.xxxtc.f37

---

## 部署包结构

```
esp-offline-deploy/
├── node/                          # Node.js v18 Linux 二进制（已包含）
│   └── node-v18.20.4-linux-x64/
├── backend/                       # 后端服务（含依赖）
│   ├── server.mjs
│   ├── package.json
│   ├── meter_ledger.csv
│   └── node_modules/              # 预安装的生产依赖
├── frontend/                      # 前端构建文件
│   └── dist/
├── nginx/                         # Nginx 离线安装包（可选）
│   └── nginx-1.24.0.tar.gz
└── install.sh                     # 一键安装脚本
```

---

## 部署步骤

### 第一步：上传文件到服务器

使用 WinSCP、FileZilla 或 MobaXterm 等 SFTP 工具，将 `esp-offline-deploy` 目录上传到服务器：

```
服务器目标路径: /opt/
上传后完整路径: /opt/esp-offline-deploy/
```

### 第二步：SSH 登录服务器并执行安装

```bash
ssh root@10.51.190.71
# 密码: rg.xxxtc.f37
```

### 第三步：运行安装脚本

```bash
cd /opt/esp-offline-deploy
chmod +x install.sh
./install.sh
```

安装脚本会自动完成：
1. 解压 Node.js 到 `/usr/local/node`
2. 配置环境变量
3. 创建项目目录
4. 复制前后端文件
5. 配置 Nginx（如已安装）
6. 创建 systemd 服务
7. 启动服务

### 第四步：验证部署

```bash
# 检查后端服务状态
systemctl status esp-backend

# 查看后端日志
journalctl -u esp-backend -f

# 测试 API
curl http://localhost:8080/api/rollers

# 访问系统
http://10.51.190.71
```

---

## 手动安装（如脚本执行失败）

### 1. 安装 Node.js

```bash
# 解压 Node.js
tar -xf /opt/esp-offline-deploy/node/node-v18.20.4-linux-x64.tar.xz -C /usr/local/

# 创建软链接
ln -sf /usr/local/node-v18.20.4-linux-x64/bin/node /usr/local/bin/node
ln -sf /usr/local/node-v18.20.4-linux-x64/bin/npm /usr/local/bin/npm

# 验证
node -v
npm -v
```

### 2. 创建项目目录

```bash
mkdir -p /opt/esp-roller-monitor/backend
mkdir -p /opt/esp-roller-monitor/frontend
```

### 3. 复制文件

```bash
# 复制后端
cp -r /opt/esp-offline-deploy/backend/* /opt/esp-roller-monitor/backend/

# 复制前端
cp -r /opt/esp-offline-deploy/frontend/dist/* /opt/esp-roller-monitor/frontend/
```

### 4. 启动后端

```bash
cd /opt/esp-roller-monitor/backend
nohup /usr/local/bin/node server.mjs > /var/log/esp-backend.log 2>&1 &
```

### 5. 配置 Nginx（如已安装）

```bash
cat > /etc/nginx/conf.d/esp-roller-monitor.conf << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        root /opt/esp-roller-monitor/frontend;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://localhost:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

nginx -t
systemctl reload nginx
```

---

## 常见问题

### Q1: Nginx 未安装

如果服务器没有 Nginx，可以：
1. 从本地下载 Nginx 源码包上传到服务器编译安装
2. 或者直接使用 Node.js 提供静态文件服务（修改 server.mjs）

### Q2: 端口被占用

```bash
# 检查端口占用
netstat -tlnp | grep 8080

# 修改后端端口
vim /opt/esp-roller-monitor/backend/server.mjs
# 修改 const PORT = 8080 为其他端口
```

### Q3: 权限问题

```bash
chmod +x /usr/local/bin/node
chmod +x /usr/local/bin/npm
```

---

## 文件清单

| 文件 | 大小 | 说明 |
|------|------|------|
| `node-v18.20.4-linux-x64.tar.xz` | ~23MB | Node.js Linux 二进制 |
| `server.mjs` | ~8KB | 后端主程序 |
| `package.json` | ~1KB | 依赖配置 |
| `meter_ledger.csv` | ~3KB | 辊道数据 |
| `node_modules/` | ~5MB | 预安装的生产依赖 |
| `frontend/dist/` | ~2MB | 前端构建文件 |

---

## 启动命令速查

```bash
# 启动后端
cd /opt/esp-roller-monitor/backend
/usr/local/bin/node server.mjs

# 后台启动
nohup /usr/local/bin/node server.mjs > /var/log/esp-backend.log 2>&1 &

# 停止后端
pkill -f "node server.mjs"

# 查看日志
tail -f /var/log/esp-backend.log
```
