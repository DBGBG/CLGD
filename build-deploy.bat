@echo off
REM ESP 层冷辊道监控系统 - Windows 打包脚本
REM 打包所有部署所需文件

setlocal enabledelayedexpansion

set "VERSION=1.0.0"
set "PACKAGE_NAME=esp-layer-cooling-%VERSION%-deploy"
set "TEMP_DIR=dist\%PACKAGE_NAME%"
set "DIST_DIR=dist"

echo.
echo ============================================
echo   ESP 系统 - 打包发布
echo ============================================
echo.

REM 检查必要文件
if not exist "backend\target\esp-layer-cooling-1.0.0.jar" (
    echo [ERROR] 缺少后端 JAR 包，请先执行 mvn clean package
    pause
    exit /b 1
)
echo [OK] backend\target\esp-layer-cooling-1.0.0.jar

if not exist "frontend\dist" (
    echo [ERROR] 缺少前端构建产物，请先执行 npm run build
    pause
    exit /b 1
)
echo [OK] frontend\dist

if not exist "meter_ledger.csv" (
    echo [ERROR] 缺少 meter_ledger.csv
    pause
    exit /b 1
)
echo [OK] meter_ledger.csv

if not exist "deploy" (
    echo [ERROR] 缺少 deploy 目录
    pause
    exit /b 1
)
echo [OK] deploy\

REM 清理并创建临时目录
if exist "%TEMP_DIR%" rmdir /s /q "%TEMP_DIR%"
mkdir "%TEMP_DIR%"

echo.
echo [INFO] 复制文件...

REM 复制后端 JAR
copy "backend\target\esp-layer-cooling-1.0.0.jar" "%TEMP_DIR%\" >nul
echo [OK] JAR 包

REM 复制前端文件
xcopy "frontend\dist" "%TEMP_DIR%\frontend\" /e /i /q >nul
echo [OK] 前端文件

REM 复制 CSV
copy "meter_ledger.csv" "%TEMP_DIR%\" >nul
echo [OK] CSV 数据

REM 复制部署文件
xcopy "deploy" "%TEMP_DIR%\deploy\" /e /i /q >nul
echo [OK] 部署配置

REM 创建版本信息
(
echo ESP Layer Cooling System
echo Version: %VERSION%
echo Build Time: %date% %time%
echo Java Version: 1.8
echo Spring Boot Version: 2.7.18
) > "%TEMP_DIR%\VERSION"

REM 创建说明
(
echo ESP 层冷辊道监控系统 - 部署包
echo ================================
echo.
echo 部署步骤:
echo.
echo 1. 将此包上传到服务器 (scp/ftp/U盘)
echo 2. 解压: tar -xzf esp-layer-cooling-1.0.0-deploy.tar.gz
echo 3. 进入目录: cd esp-layer-cooling-1.0.0-deploy
echo 4. 执行部署: chmod +x deploy/scripts/*.sh ^&^& ./deploy/scripts/deploy.sh 服务器IP
echo.
echo 详细说明请查看: deploy/DEPLOY.md
) > "%TEMP_DIR%\README"

REM 创建 dist 目录
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

REM 打包 (使用 7zip 如果可用，否则使用 tar)
echo.
echo [INFO] 打包中...

where 7z >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    cd "%DIST_DIR%"
    7z a -tzip "%PACKAGE_NAME%.zip" "%PACKAGE_NAME%\"
    cd ..
    set "EXT=zip"
) else (
    cd "%DIST_DIR%"
    tar -czf "%PACKAGE_NAME%.tar.gz" "%PACKAGE_NAME%\"
    cd ..
    set "EXT=tar.gz"
)

REM 获取文件大小
for %%A in ("%DIST_DIR%\%PACKAGE_NAME%.%EXT%") do set "SIZE=%%~zA"
set /a "SIZE_MB=!SIZE!/1048576"

echo.
echo ============================================
echo   打包完成！
echo ============================================
echo.
echo 输出文件: %DIST_DIR%\%PACKAGE_NAME%.%EXT%
echo 文件大小: !SIZE_MB! MB
echo.
echo 上传命令:
echo   scp %DIST_DIR%\%PACKAGE_NAME%.%EXT% root@服务器IP:/tmp/
echo.
echo 服务器上执行:
echo   cd /tmp ^&^& tar -xzf %PACKAGE_NAME%.tar.gz
echo   cd %PACKAGE_NAME%
echo   chmod +x deploy/scripts/*.sh
echo   ./deploy/scripts/deploy.sh 服务器IP
echo.

REM 清理临时目录
rmdir /s /q "%TEMP_DIR%"

pause
