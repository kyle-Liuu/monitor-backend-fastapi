@echo off
rem 设置控制台编码为UTF-8
chcp 65001 >nul

echo =============================================
echo AI智能监控系统后端启动脚本
echo =============================================

echo 确保当前目录是项目根目录...

if not exist app\main.py (
    echo 错误: 找不到主应用入口文件。
    echo 请确保您在backend目录下运行此脚本。
    exit /b 1
)

echo 请选择操作^:
echo 1. 启动服务
echo 2. 重置数据库并启动服务
echo 3. 退出程序

set /p option="请输入选项 (1/2/3)^: "

if "%option%"=="3" (
    echo 已退出系统。
    exit /b 0
) else if "%option%"=="2" (
    echo 警告^: 此操作将删除现有数据库并重新创建^!
    echo 所有现有数据将丢失^!
    
    set /p confirm="是否确认重置数据库^? (Y/N)^: "
    
    if /i "%confirm%"=="N" (
        echo 已取消重置数据库操作。
        pause
        exit /b 0
    ) else if /i "%confirm%"=="Y" (
        echo 正在重置数据库...
        python reset_db.py
        
        if %ERRORLEVEL% EQU 0 (
            echo 数据库重置成功。默认用户^:
            echo   超级管理员^: super (密码^: 123456)
            echo   管理员^: admin (密码^: 123456)
            echo   普通用户^: user (密码^: 123456)
            echo.
            echo 正在启动后端服务...
            echo =============================================
            echo API文档地址^:
            echo - Swagger UI^: http://127.0.0.1:8000/docs
            echo - ReDoc^:      http://127.0.0.1:8000/redoc
            echo =============================================
            python run.py
        ) else (
            echo 数据库重置失败，请检查错误信息。
            pause
            exit /b 1
        )
    ) else (
        echo 无效的选择，请输入Y或N。
        pause
        exit /b 1
    )
) else if "%option%"=="1" (
    echo 正在启动后端服务...
    echo =============================================
    echo API文档地址^:
    echo - Swagger UI^: http://127.0.0.1:8000/docs
    echo - ReDoc^:      http://127.0.0.1:8000/redoc
    echo =============================================
    python run.py
) else (
    echo 无效的选项，请输入1、2或3。
    pause
    exit /b 1
)

echo 如果服务启动失败，请尝试^:
echo 1. 检查是否安装了所有依赖^: pip install -r requirements.txt
echo 2. 手动重置数据库^: python reset_db.py

pause 