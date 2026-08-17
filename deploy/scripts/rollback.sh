#!/bin/bash
# ESP 层冷辊道监控系统 - 回滚脚本

APP_HOME="/opt/esp-layer-cooling"
BACKUP_DIR="${APP_HOME}/backup"
APP_NAME="esp-layer-cooling"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
log_info "ESP 系统 - 回滚操作"
echo ""

# 检查备份目录
if [ ! -d "$BACKUP_DIR" ]; then
    log_error "备份目录不存在: $BACKUP_DIR"
    exit 1
fi

# 显示可用备份
echo "可用备份:"
echo "----------"
ls -lt "$BACKUP_DIR"
echo ""

# 选择备份
read -p "请输入要回滚的备份目录名 (例如 backup_20260803): " BACKUP_NAME

if [ ! -d "${BACKUP_DIR}/${BACKUP_NAME}" ]; then
    log_error "备份不存在: ${BACKUP_NAME}"
    exit 1
fi

# 确认
read -p "确认回滚到 ${BACKUP_NAME}? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    log_info "已取消"
    exit 0
fi

# 停止服务
log_info "停止服务..."
systemctl stop "${APP_NAME}-backend"

# 回滚后端
if [ -f "${BACKUP_DIR}/${BACKUP_NAME}/esp-layer-cooling-1.0.0.jar" ]; then
    log_info "回滚后端 JAR 包..."
    cp "${BACKUP_DIR}/${BACKUP_NAME}/esp-layer-cooling-1.0.0.jar" "${APP_HOME}/backend/"
fi

# 回滚前端
if [ -d "${BACKUP_DIR}/${BACKUP_NAME}/frontend" ]; then
    log_info "回滚前端文件..."
    rm -rf "${APP_HOME}/frontend"/*
    cp -r "${BACKUP_DIR}/${BACKUP_NAME}/frontend"/* "${APP_HOME}/frontend/"
fi

# 启动服务
log_info "启动服务..."
systemctl start "${APP_NAME}-backend"
sleep 3

if systemctl is-active --quiet "${APP_NAME}-backend"; then
    log_info "回滚成功！服务已启动"
else
    log_error "回滚失败，服务无法启动"
fi

echo ""
