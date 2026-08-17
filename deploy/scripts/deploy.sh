#!/bin/bash
# ESP 层冷辊道监控系统 - Rocky Linux 部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh [服务器IP或域名]

set -e

# ==================== 配置参数 ====================
APP_NAME="esp-layer-cooling"
APP_HOME="/opt/${APP_NAME}"
BACKEND_DIR="${APP_HOME}/backend"
FRONTEND_DIR="${APP_HOME}/frontend"
DATA_DIR="${APP_HOME}/data"
LOGS_DIR="${APP_HOME}/logs"

# 源文件路径 (相对于项目根目录)
SOURCE_JAR="backend/target/esp-layer-cooling-1.0.0.jar"
SOURCE_FRONTEND="frontend/dist"
SOURCE_CSV="meter_ledger.csv"
SOURCE_CONFIG="deploy/application-prod.properties"
SOURCE_SERVICE="deploy/esp-backend.service"
SOURCE_NGINX="deploy/esp-nginx.conf"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==================== 检查环境 ====================
check_env() {
    log_info "检查运行环境..."
    
    # 检查 Java
    if ! command -v java &> /dev/null; then
        log_error "未检测到 Java，请先安装 JDK 8"
        exit 1
    fi
    
    JAVA_VERSION=$(java -version 2>&1 | head -1 | awk -F'"' '{print $2}')
    log_info "Java 版本: $JAVA_VERSION"
    
    # 检查 JDK 8
    if [[ ! "$JAVA_VERSION" == 1.8.* ]]; then
        log_warn "建议使用 JDK 8，当前版本: $JAVA_VERSION"
    fi
    
    # 检查 Nginx
    if ! command -v nginx &> /dev/null; then
        log_error "未检测到 Nginx，请先安装"
        exit 1
    fi
    log_info "Nginx 版本: $(nginx -v 2>&1)"
    
    # 检查是否 root
    if [[ $EUID -ne 0 ]]; then
        log_warn "建议使用 root 用户部署 (sudo bash)"
    fi
}

# ==================== 安装 JDK 8 ====================
install_jdk() {
    if command -v java &> /dev/null; then
        log_info "Java 已安装，跳过..."
        return
    fi
    
    log_info "安装 JDK 8..."
    dnf install -y java-1.8.0-openjdk java-1.8.0-openjdk-devel
    log_info "JDK 8 安装完成"
}

# ==================== 安装 Nginx ====================
install_nginx() {
    if command -v nginx &> /dev/null; then
        log_info "Nginx 已安装，跳过..."
        return
    fi
    
    log_info "安装 Nginx..."
    dnf install -y epel-release
    dnf install -y nginx
    
    # 启动并设置开机自启
    systemctl start nginx
    systemctl enable nginx
    
    log_info "Nginx 安装完成"
}

# ==================== 创建目录结构 ====================
create_dirs() {
    log_info "创建目录结构..."
    
    mkdir -p "${BACKEND_DIR}"
    mkdir -p "${FRONTEND_DIR}"
    mkdir -p "${DATA_DIR}"
    mkdir -p "${LOGS_DIR}"
    
    log_info "目录结构:"
    log_info "  ${APP_HOME}/"
    log_info "  ├── backend/     (Spring Boot JAR)"
    log_info "  ├── frontend/    (前端静态文件)"
    log_info "  ├── data/        (数据文件)"
    log_info "  └── logs/        (日志文件)"
}

# ==================== 部署后端 ====================
deploy_backend() {
    log_info "部署后端服务..."
    
    # 复制 JAR 包
    if [ -f "$SOURCE_JAR" ]; then
        cp "$SOURCE_JAR" "${BACKEND_DIR}/"
        log_info "JAR 包已复制"
    else
        log_error "找不到 JAR 包: $SOURCE_JAR"
        log_error "请先在本地执行: mvn clean package -DskipTests"
        exit 1
    fi
    
    # 复制配置文件
    if [ -f "$SOURCE_CONFIG" ]; then
        cp "$SOURCE_CONFIG" "${BACKEND_DIR}/application-prod.properties"
        log_info "配置文件已复制"
    fi
    
    # 复制 CSV 文件
    if [ -f "$SOURCE_CSV" ]; then
        cp "$SOURCE_CSV" "${DATA_DIR}/"
        log_info "CSV 数据已复制"
    else
        log_warn "找不到 CSV 文件: $SOURCE_CSV"
        log_warn "请手动将 meter_ledger.csv 放到 ${DATA_DIR}/"
    fi
}

# ==================== 部署前端 ====================
deploy_frontend() {
    log_info "部署前端文件..."
    
    if [ -d "$SOURCE_FRONTEND" ]; then
        cp -r "$SOURCE_FRONTEND"/* "${FRONTEND_DIR}/"
        log_info "前端文件已复制"
    else
        log_error "找不到前端构建产物: $SOURCE_FRONTEND"
        log_error "请先在本地执行: npm run build"
        exit 1
    fi
}

# ==================== 配置 Systemd ====================
setup_systemd() {
    log_info "配置 systemd 服务..."
    
    if [ -f "$SOURCE_SERVICE" ]; then
        cp "$SOURCE_SERVICE" "/etc/systemd/system/${APP_NAME}-backend.service"
        
        # 更新配置文件中的路径
        sed -i "s|/opt/esp-layer-cooling|${APP_HOME}|g" "/etc/systemd/system/${APP_NAME}-backend.service"
        
        systemctl daemon-reload
        log_info "systemd 服务配置完成"
    else
        log_error "找不到服务配置文件: $SOURCE_SERVICE"
        exit 1
    fi
}

# ==================== 配置 Nginx ====================
setup_nginx() {
    log_info "配置 Nginx..."
    
    if [ -f "$SOURCE_NGINX" ]; then
        cp "$SOURCE_NGINX" "/etc/nginx/conf.d/${APP_NAME}.conf"
        
        # 更新路径
        sed -i "s|/opt/esp-layer-cooling|${APP_HOME}|g" "/etc/nginx/conf.d/${APP_NAME}.conf"
        
        # 测试配置
        nginx -t
        systemctl reload nginx
        
        log_info "Nginx 配置完成"
    else
        log_error "找不到 Nginx 配置文件: $SOURCE_NGINX"
        exit 1
    fi
}

# ==================== 配置防火墙 ====================
setup_firewall() {
    log_info "配置防火墙..."
    
    if command -v firewall-cmd &> /dev/null; then
        firewall-cmd --permanent --add-port=80/tcp
        firewall-cmd --permanent --add-port=8080/tcp
        firewall-cmd --reload
        log_info "防火墙已开放 80 和 8080 端口"
    else
        log_warn "firewalld 未运行，请手动开放端口"
    fi
}

# ==================== 启动服务 ====================
start_services() {
    log_info "启动后端服务..."
    
    systemctl start "${APP_NAME}-backend"
    sleep 3
    
    if systemctl is-active --quiet "${APP_NAME}-backend"; then
        log_info "后端服务启动成功"
    else
        log_error "后端服务启动失败，查看日志: journalctl -u ${APP_NAME}-backend -e"
        exit 1
    fi
    
    log_info "重启 Nginx..."
    systemctl restart nginx
    
    log_info ""
    log_info "============================================"
    log_info "  部署完成！"
    log_info "============================================"
    log_info ""
    log_info "服务地址:"
    log_info "  前端页面: http://服务器IP/"
    log_info "  后端 API: http://服务器IP:8080/api/"
    log_info ""
    log_info "管理命令:"
    log_info "  查看状态: systemctl status ${APP_NAME}-backend"
    log_info "  查看日志: journalctl -u ${APP_NAME}-backend -f"
    log_info "  重启服务: systemctl restart ${APP_NAME}-backend"
    log_info "  停止服务: systemctl stop ${APP_NAME}-backend"
    log_info ""
}

# ==================== 主流程 ====================
main() {
    echo ""
    log_info "ESP 层冷辊道监控系统 - Rocky Linux 部署脚本"
    echo ""
    
    # 检查参数
    SERVER_IP=${1:-"服务器IP"}
    
    # 执行部署步骤
    install_jdk
    install_nginx
    check_env
    create_dirs
    deploy_backend
    deploy_frontend
    setup_systemd
    setup_nginx
    setup_firewall
    start_services
    
    echo ""
    log_info "请访问: http://${SERVER_IP}/"
    echo ""
}

# 执行主流程
main "$@"
