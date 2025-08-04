@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 运行重构后的单元测试
echo ========================================
echo.

REM 设置环境变量
set PYTHONPATH=%CD%

echo 1. 运行所有测试...
echo ----------------------------------------
python -m unittest discover -s tests -v
if %errorlevel% neq 0 (
    echo ❌ 部分测试失败
    pause
    exit /b 1
) else (
    echo ✅ 所有测试通过
)

echo.
echo 🎉 所有重构后的单元测试执行完成！
echo.
echo 测试覆盖的功能模块：
echo   - ✅ 告警自动处理 (alarm_processor)
echo   - ✅ 视频录制和片段保存 (video_recorder) 
echo   - ✅ WebSocket实时通信 (websocket_manager)
echo   - ✅ 配置管理 (config)
echo   - ✅ 分析器服务集成 (analyzer_service)
echo   - ✅ 流管理模块 (stream_module)
echo   - ✅ 任务管理模块 (task_module)
echo   - ✅ 算法模块 (algorithm_module)
echo   - ✅ 告警模块 (alarm_module)
echo   - ✅ 输出模块 (output_module)
echo   - ✅ 数据访问层 (dao)
echo   - ✅ 事件总线 (event_bus)
echo   - ✅ 共享内存 (shared_memory)
echo   - ✅ ID生成器 (id_generator)
echo   - ✅ 工作进程 (worker_processes)
echo.
echo ========================================
echo 📊 测试覆盖率报告生成指南
echo ========================================
echo.
echo 步骤1: 安装coverage工具
echo   conda activate rkyolo11
echo   pip install coverage
echo.
echo 步骤2: 运行测试并收集覆盖率数据
echo   coverage run --source=app -m unittest discover -s tests -v
echo.
echo 步骤3: 生成命令行覆盖率报告
echo   coverage report --show-missing
echo.
echo 步骤4: 生成HTML详细报告
echo   coverage html
echo.
echo 步骤5: 查看详细HTML报告
echo   start htmlcov\index.html
echo   (或手动打开 htmlcov\index.html 文件)
echo.
echo 步骤6: 生成XML报告 (可选)
echo   coverage xml
echo.
echo ========================================
echo 📈 覆盖率报告分析指南
echo ========================================
echo.
echo 🎯 覆盖率指标说明：
echo   - Statements: 代码语句总数
echo   - Missing: 未执行的语句数
echo   - Coverage: 覆盖率百分比 (越高越好)
echo.
echo 📊 覆盖率质量标准：
echo   - 90%+ : 优秀 ✅
echo   - 80-90%: 良好 ⭐
echo   - 70-80%: 一般 ⚠️
echo   - <70% : 需要改进 ❌
echo.
echo 🔍 重点关注文件：
echo   - app/core/*.py      (核心功能模块)
echo   - app/api/*.py       (API接口层)
echo   - app/db/*.py        (数据库层)
echo   - app/schemas/*.py   (数据模型)
echo.
echo 📋 分析重点：
echo   1. 查看总体覆盖率是否达标
echo   2. 识别覆盖率低的关键模块
echo   3. 检查核心业务逻辑覆盖情况
echo   4. 关注错误处理代码覆盖率
echo   5. 验证边界条件测试覆盖
echo.
echo 🚀 快速生成报告命令：
echo   coverage run --source=app -m unittest discover -s tests && coverage html && start htmlcov\index.html
echo.
pause 