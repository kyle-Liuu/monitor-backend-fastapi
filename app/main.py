"""
FastAPI 主应用模块，配置API路由和初始化服务。
"""

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
import logging
import json
from typing import List, Dict
import asyncio
import signal
import sys
import os
import threading

from .core.analyzer.analyzer_service import AnalyzerService
from .api.router import api_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="AI视频监控系统",
    description="智能监控与视频分析系统API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应设置为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 - 使用统一的api_router
app.include_router(api_router, prefix="/api")

# 全局视频分析器服务
analyzer_service = AnalyzerService.get_instance()

# 应用状态
app_state = {"is_shutting_down": False}

# 导入统一的WebSocket管理器
from app.core.websocket_manager import unified_ws_manager
from app.api.endpoints.websocket_status import status_broadcast_task

# 自定义异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "请求参数验证失败", "errors": exc.errors()},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "message": str(exc)},
    )

# 优雅关闭处理
async def handle_shutdown(app_state):
    """处理应用关闭"""
    if app_state["is_shutting_down"]:
        logger.warning("检测到重复关闭请求，将强制退出...")
        os._exit(0)
    
    logger.info("应用正在关闭...")
    app_state["is_shutting_down"] = True
    
    # 极短的超时后强制退出
    def force_exit():
        logger.warning("应用关闭超时，强制退出...")
        os._exit(0)
    
    # 仅等待1秒
    timer = threading.Timer(1.0, force_exit)
    timer.daemon = True
    timer.start()
    
    try:
        # 停止关键服务
        analyzer_service.stop()
        
        # 尝试清理WebSocket连接
        try:
            await unified_ws_manager.close_all_connections()
            logger.info("已清理WebSocket连接")
        except Exception as e:
            logger.error(f"清理WebSocket连接失败: {e}")
            pass
        
        logger.info("应用清理完成")
    except Exception as e:
        logger.error(f"关闭过程中发生错误: {e}")
        # 错误时直接退出
        os._exit(0)

# 启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("应用启动，初始化服务...")
    # 初始化视频分析器服务
    analyzer_service.start()
    # 启动WebSocket状态广播任务
    asyncio.create_task(status_broadcast_task(), name="status_broadcast_task")

# 关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("应用关闭，停止服务...")
    await handle_shutdown(app_state)

# WebSocket统一管理
# 状态广播任务现在在websocket_status.py中定义和管理

# WebSocket路由 - 告警通知 (已移至websocket_alarms.py)
# @app.websocket("/ws/alarms")
# async def websocket_alarm_endpoint(websocket: WebSocket):
#     await manager.connect(websocket, "alarms")
#     try:
#         while True:
#             # 保持连接活跃，实际数据由告警处理进程推送
#             await websocket.receive_text()
#     except WebSocketDisconnect:
#         manager.disconnect(websocket, "alarms")
#     except Exception as e:
#         logger.error(f"告警WebSocket异常: {e}")
#         manager.disconnect(websocket, "alarms")

# WebSocket路由 - 状态更新 (已移至websocket_status.py)
# 所有WebSocket端点现在通过api_router统一管理

# 测试路由
@app.get("/")
def read_root():
    return {
        "message": "AI视频监控系统API服务运行中",
        "status": "ok",
        "version": "1.0.0"
    } 