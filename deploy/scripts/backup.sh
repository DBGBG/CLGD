#!/bin/bash
# ESP 层冷辊道监控系统 - 备份脚本

APP_HOME="/opt/esp-layer-cooling"
BACKUP_DIR="${APP_HOME}/backup"
BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }

echo ""
log_info "ESP 系统 - 备份"
echo ""

# 创建备份目录
mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}"

# 备份后端
if [ -f "${APP_HOME}/backend/esp-layer-cooling-1.0.0.jar" ]; then
    cp "${APP_HOME}/backend/esp-layer-cooling-1.0.0.jar" "${BACKUP_DIR}/${BACKUP_NAME}/"
    log_info "后端 JAR 包已备份"
fi

# 备份前端
if [ -d "${APP_HOME}/frontend" ]; then
    mkdir -p "${BACKUP_DIR}/${BACKUP_NAME}/frontend"
    cp -r "${APP_HOME}/frontend"/* "${BACKUP_DIR}/${BACKUP_NAME}/frontend/"
    log_info "前端文件已备份"
fi

# 清理旧备份 (保留最近10个)
cd "$BACKUP_DIR"
ls -dt backup_* | tail -n +11 | xargs rm -rf 2>/dev/null

log_info "备份完成: ${BACKUP_DIR}/${BACKUP_NAME}"
echo ""
