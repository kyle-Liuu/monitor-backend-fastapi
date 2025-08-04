@echo off
rem 设置控制台编码为UTF-8
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo =============================================
echo AI监控系统后端启动脚本 v2.2
echo =============================================

echo 确保当前目录是项目根目录...

if not exist app\main.py (
    echo 错误: 找不到主应用入口文件。
    echo 请确保您在backend目录下运行此脚本。
    pause
    exit /b 1
)

:menu
echo.
echo 请选择操作:
echo 1. 启动服务
echo 2. 重置数据库并启动服务
echo 3. 退出程序

set /p option="请输入选项 (1/2/3): "

if "%option%"=="3" (
    echo 已退出系统。
    exit /b 0
)

if "%option%"=="2" (
    echo 正在重置数据库...
    python reset_db.py
    if %ERRORLEVEL% EQU 0 (
        echo 数据库重置成功。默认用户:
        echo   超级管理员: super ^(密码: 123456^) ^[角色: R_SUPER^]
        echo   管理员: admin ^(密码: 123456^) ^[角色: R_ADMIN^]
        echo   普通用户: user ^(密码: 123456^) ^[角色: R_USER^]
        echo.
        echo 默认数据:
        echo   - 3个系统角色 ^(R_SUPER, R_ADMIN, R_USER^)
        echo   - 示例组织结构 ^(总部-^>A栋/B栋^)
        echo   - 完整菜单权限配置
        echo.
        echo 正在启动 MediaServer ...
        tasklist /FI "IMAGENAME eq MediaServer.exe" | find /I "MediaServer.exe" >nul
        if errorlevel 1 (
            echo 未检测到 MediaServer，正在启动...
            if exist "zlm\Release\MediaServer.exe" (
                start "" "zlm\Release\MediaServer.exe"
            ) else (
                if exist "zlm\MediaServer.exe" (
                    start "" "zlm\MediaServer.exe"
                ) else (
                    echo 警告: MediaServer.exe 不存在，跳过启动。
                )
            )
        ) else (
            echo MediaServer 已在运行，无需重复启动。
        )
        echo 正在启动后端服务...
        echo =============================================
        echo API文档地址:
        echo - Swagger UI: http://127.0.0.1:8001/docs
        echo - ReDoc:      http://127.0.0.1:8001/redoc
        echo =============================================
        python run.py
    ) else (
        echo 数据库重置失败，请检查错误信息。
        pause
        goto menu
    )
)

if "%option%"=="1" (
    echo 正在检查系统状态...
    
    if not exist app.db (
        echo 警告: 数据库文件不存在，建议先重置数据库
        set /p auto_reset="是否自动重置数据库? (Y/N): "
        if /i "%auto_reset%"=="Y" (
            echo 正在自动重置数据库...
            python reset_db.py
            if %ERRORLEVEL% NEQ 0 (
                echo 数据库重置失败，请手动重置
                pause
                goto menu
            )
        )
    )
    
    echo 正在启动 MediaServer ...
    tasklist /FI "IMAGENAME eq MediaServer.exe" | find /I "MediaServer.exe" >nul
    if errorlevel 1 (
        echo 未检测到 MediaServer，正在启动...
        if exist "zlm\Release\MediaServer.exe" (
            start "" "zlm\Release\MediaServer.exe"
        ) else (
            if exist "zlm\MediaServer.exe" (
                start "" "zlm\MediaServer.exe"
            ) else (
                echo 警告: MediaServer.exe 不存在，跳过启动。
            )
        )
    ) else (
        echo MediaServer 已在运行，无需重复启动。
    )
    
    echo 正在启动后端服务...
    echo =============================================
    echo API文档地址:
    echo - Swagger UI: http://127.0.0.1:8001/docs
    echo - ReDoc:      http://127.0.0.1:8001/redoc
    echo =============================================
    python run.py
)

if not "%option%"=="1" if not "%option%"=="2" if not "%option%"=="3" (
    echo 无效的选项，请输入1、2或3。
    pause
    goto menu
)

:end
echo.
echo 日志文件:
echo - API日志: logs\app.log
echo.
echo 系统信息:
echo - 数据库文件: app.db
echo - 配置文件: config.yaml
echo - 临时目录: temp_frames, output, logs
echo.
pause 