#!/bin/bash
# ESP 层冷辊道监控系统 - 快速更新脚本
# 仅更新 JAR 包和前端文件，不重新配置环境

set -e

APP_HOME="/opt/esp-layer-cooling"
BACKEND_DIR="${APP_HOME}/backend"
FRONTEND_DIR="${APP_HOME}/frontend"
APP_NAME="esp-layer-cooling"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
log_info "ESP 系统 - 快速更新"
echo ""

# 检查目录
if [ ! -d "$APP_HOME" ]; then
    log_error "部署目录不存在: $APP_HOME"
    log_error "请先执行完整部署脚本"
    exit 1
fi

# 更新后端
if [ -f "backend/target/esp-layer-cooling-1.0.0.jar" ]; then
    log_info "更新后端 JAR 包..."
    cp backend/target/esp-layer-cooling-1.0.0.jar "${BACKEND_DIR}/"
    log_info "后端 JAR 包已更新"
else
    log_error "找不到 JAR 包"
fi

# 更新前端
if [ -d "frontend/dist" ]; then
    log_info "更新前端文件..."
    rm -rf "${FRONTEND_DIR}"/*
    cp -r frontend/dist/* "${FRONTEND_DIR}/"
    log_info "前端文件已更新"
else
    log_error "找不到前端构建产物"
fi

# 重启服务
log_info "重启后端服务..."
systemctl restart "${APP_NAME}-backend"

sleep 3

if systemctl is-active --quiet "${APP_NAME}-backend"; then
    log_info "后端服务重启成功"
else
    log_error "后端服务启动失败"
fi

log_info "重载 Nginx..."
systemctl reload nginx

echo ""
log_info "更新完成！"
echo ""
