#!/bin/bash
# ESP 层冷辊道监控系统 - 本地环境检查脚本
# 用于在本地验证构建产物

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

OK="${GREEN}[✓]${NC}"
WARN="${YELLOW}[!]${NC}"
FAIL="${RED}[✗]${NC}"

echo ""
echo "============================================"
echo "  ESP 系统 - 本地环境检查"
echo "============================================"
echo ""

ERRORS=0
WARNINGS=0

# 检查 Java
echo "--- Java 环境 ---"
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -1 | awk -F'"' '{print $2}')
    if [[ "$JAVA_VERSION" == 1.8.* ]]; then
        echo -e "$OK Java: $JAVA_VERSION"
    else
        echo -e "$WARN Java: $JAVA_VERSION (建议使用 JDK 8)"
        ((WARNINGS++))
    fi
else
    echo -e "$FAIL Java 未安装"
    ((ERRORS++))
fi

# 检查 Maven
echo ""
echo "--- Maven 环境 ---"
if command -v mvn &> /dev/null; then
    MVN_VERSION=$(mvn --version 2>&1 | head -1)
    echo -e "$OK Maven: $MVN_VERSION"
else
    echo -e "$WARN Maven 未安装 (不需要，构建已完成)"
    ((WARNINGS++))
fi

# 检查 Node.js
echo ""
echo "--- Node.js 环境 ---"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "$OK Node.js: $NODE_VERSION"
else
    echo -e "$WARN Node.js 未安装 (不需要，构建已完成)"
    ((WARNINGS++))
fi

# 检查后端 JAR
echo ""
echo "--- 后端构建 ---"
if [ -f "backend/target/esp-layer-cooling-1.0.0.jar" ]; then
    JAR_SIZE=$(du -h backend/target/esp-layer-cooling-1.0.0.jar | cut -f1)
    echo -e "$OK JAR 包存在: backend/target/esp-layer-cooling-1.0.0.jar ($JAR_SIZE)"
else
    echo -e "$FAIL JAR 包不存在，请先执行: mvn clean package -DskipTests"
    ((ERRORS++))
fi

# 检查前端构建
echo ""
echo "--- 前端构建 ---"
if [ -d "frontend/dist" ]; then
    if [ -f "frontend/dist/index.html" ]; then
        echo -e "$OK 前端构建存在: frontend/dist/"
        echo -e "    index.html"
        echo -e "    assets/ ($(ls frontend/dist/assets | wc -l) 个文件)"
    else
        echo -e "$FAIL 前端构建不完整"
        ((ERRORS++))
    fi
else
    echo -e "$FAIL 前端构建不存在，请先执行: npm run build"
    ((ERRORS++))
fi

# 检查 CSV 文件
echo ""
echo "--- 数据文件 ---"
if [ -f "meter_ledger.csv" ]; then
    CSV_LINES=$(wc -l < meter_ledger.csv)
    echo -e "$OK CSV 文件存在: meter_ledger.csv ($CSV_LINES 行)"
else
    echo -e "$WARN CSV 文件不存在，请将 meter_ledger.csv 复制到项目根目录"
    ((WARNINGS++))
fi

# 检查部署文件
echo ""
echo "--- 部署文件 ---"
DEPLOY_FILES=(
    "deploy/esp-backend.service"
    "deploy/esp-nginx.conf"
    "deploy/application-prod.properties"
    "deploy/scripts/deploy.sh"
    "deploy/scripts/update.sh"
    "deploy/scripts/backup.sh"
    "deploy/scripts/rollback.sh"
    "deploy/DEPLOY.md"
)

for file in "${DEPLOY_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "$OK $file"
    else
        echo -e "$FAIL $file"
        ((ERRORS++))
    fi
done

# 汇总
echo ""
echo "============================================"
echo "  检查结果"
echo "============================================"
echo ""
echo -e "  错误: ${RED}$ERRORS${NC}"
echo -e "  警告: ${YELLOW}$WARNINGS${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ 环境检查通过，可以进行打包部署${NC}"
    echo ""
    echo "下一步:"
    echo "  Windows: 双击 build-deploy.bat"
    echo "  Linux/Mac: chmod +x build-deploy.sh && ./build-deploy.sh"
else
    echo -e "${RED}✗ 存在 $ERRORS 个错误，请修复后再打包${NC}"
    exit 1
fi
echo ""
