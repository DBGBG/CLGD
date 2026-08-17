#!/bin/bash
# ESP 层冷辊道监控系统 - 打包发布脚本
# 打包所有部署所需文件

set -e

VERSION="1.0.0"
PACKAGE_NAME="esp-layer-cooling-${VERSION}-deploy"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
log_info "ESP 系统 - 打包发布"
echo ""

# 检查必要文件
check_file() {
    if [ ! -f "$1" ] && [ ! -d "$1" ]; then
        log_error "缺少文件/目录: $1"
        exit 1
    fi
    log_info "✓ $1"
}

log_info "检查构建产物..."
check_file "backend/target/esp-layer-cooling-1.0.0.jar"
check_file "frontend/dist"
check_file "meter_ledger.csv"
check_file "deploy"

# 创建临时目录
TEMP_DIR="dist/${PACKAGE_NAME}"
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR"

log_info "复制文件..."

# 复制后端 JAR
cp "backend/target/esp-layer-cooling-1.0.0.jar" "$TEMP_DIR/"

# 复制前端文件
cp -r "frontend/dist" "$TEMP_DIR/frontend"

# 复制 CSV
cp "meter_ledger.csv" "$TEMP_DIR/"

# 复制部署文件
cp -r "deploy" "$TEMP_DIR/"

# 创建版本信息
cat > "$TEMP_DIR/VERSION" << EOF
ESP Layer Cooling System
Version: ${VERSION}
Build Time: $(date "+%Y-%m-%d %H:%M:%S")
Java Version: 1.8
Spring Boot Version: 2.7.18
EOF

# 创建说明文件
cat > "$TEMP_DIR/README" << 'EOF'
ESP 层冷辊道监控系统 - 部署包
================================

部署步骤:

1. 将此包上传到服务器 (scp/ftp/U盘)
2. 解压: tar -xzf esp-layer-cooling-1.0.0-deploy.tar.gz
3. 进入目录: cd esp-layer-cooling-1.0.0-deploy
4. 执行部署: chmod +x deploy/scripts/*.sh && ./deploy/scripts/deploy.sh 服务器IP

详细说明请查看: deploy/DEPLOY.md
EOF

# 打包
DIST_DIR="dist"
mkdir -p "$DIST_DIR"

cd dist
tar -czf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}/"
cd ..

# 显示结果
PACKAGE_SIZE=$(du -h "dist/${PACKAGE_NAME}.tar.gz" | cut -f1)

echo ""
log_info "============================================"
log_info "  打包完成！"
log_info "============================================"
echo ""
log_info "输出文件: dist/${PACKAGE_NAME}.tar.gz"
log_info "文件大小: ${PACKAGE_SIZE}"
echo ""
log_info "上传命令:"
log_info "  scp dist/${PACKAGE_NAME}.tar.gz root@服务器IP:/tmp/"
echo ""
log_info "服务器上执行:"
log_info "  cd /tmp && tar -xzf ${PACKAGE_NAME}.tar.gz"
log_info "  cd ${PACKAGE_NAME}"
log_info "  chmod +x deploy/scripts/*.sh"
log_info "  ./deploy/scripts/deploy.sh 服务器IP"
echo ""

# 清理临时目录
rm -rf "$TEMP_DIR"
