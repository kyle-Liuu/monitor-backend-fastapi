from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
from typing import Callable
import asyncio

from app.api.router import api_router
from app.core.config import settings
from app.db.database import init_db, get_db
from app.utils.logger import app_logger, access_logger
from app.utils.token_cleanup import schedule_token_cleanup

# 启动事件上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    app_logger.info("应用启动，开始初始化数据库...")
    await init_db()
    app_logger.info("数据库初始化完成")
    
    # 启动令牌清理任务
    app_logger.debug("启动令牌清理任务...")
    asyncio.create_task(schedule_token_cleanup(get_db))
    
    # 显示启动成功信息
    app_logger.info(f"API服务 {settings.PROJECT_NAME} v{settings.API_VERSION} 已成功启动")
    
    yield
    # 关闭时执行
    app_logger.info("应用关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    description="AI智能监控系统后端API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 配置CORS
# 如果没有设置CORS源，默认允许所有源
origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS] if settings.BACKEND_CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# 添加请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable) -> Response:
    start_time = time.time()
    
    # 处理请求前的日志 - 只在debug级别记录
    client_host = request.client.host if request.client else "unknown"
    app_logger.debug(f"请求开始: {request.method} {request.url.path} - 客户端: {client_host}")
    
    # 执行请求
    response = await call_next(request)
    
    # 处理请求后的日志
    process_time = time.time() - start_time
    log_dict = {
        "client_addr": client_host,
        "method": request.method,
        "url": request.url.path,
        "status_code": response.status_code,
    }
    
    # 使用不同级别记录日志，简化正常请求的日志
    if response.status_code >= 500:
        access_logger.error(f"请求错误 - 处理时间: {process_time:.3f}s", extra=log_dict)
    elif response.status_code >= 400:
        access_logger.warning(f"客户端错误 - 处理时间: {process_time:.3f}s", extra=log_dict)
    else:
        # 对于正常请求，只记录路径和状态码，减少日志冗余
        access_logger.info(f"{request.method} {request.url.path} - {response.status_code}")
    
    return response

# 全局异常处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    app_logger.warning(f"请求验证错误: {exc.errors()}")
    # 处理表单数据请求验证错误，确保错误可以被正确序列化为JSON
    errors = []
    for error in exc.errors():
        error_copy = dict(error)
        # 如果输入是bytes类型，转换为字符串
        if isinstance(error_copy.get('input'), bytes):
            error_copy['input'] = error_copy['input'].decode('utf-8')
        errors.append(error_copy)
    
    return JSONResponse(
        status_code=422,
        content={"code": 422, "msg": "请求参数错误", "errors": errors},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    app_logger.warning(f"HTTP异常: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    app_logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "服务器内部错误"},
    )

# 注册API路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """
    根路径，显示欢迎信息
    """
    return {
        "message": f"欢迎使用{settings.PROJECT_NAME} API",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return {"status": "ok", "version": settings.API_VERSION}


if __name__ == "__main__":
    import uvicorn
    app_logger.info("使用main.py直接启动服务")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, access_log=False) 