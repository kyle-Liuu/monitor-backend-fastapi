import uvicorn
import logging
from app.core.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("正在启动AI智能监控系统后端API服务...")
    
    # 显示API文档地址
    host = "127.0.0.1"
    port = 8000
    
    print("\n" + "="*60)
    print(f"API服务已启动: http://{host}:{port}")
    print(f"API文档地址:")
    print(f"  - Swagger UI: http://{host}:{port}/docs")
    print(f"  - ReDoc:      http://{host}:{port}/redoc")
    print("="*60 + "\n")
    
    # 启动服务，禁用标准访问日志，因为我们有自定义的日志中间件
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        access_log=False
    ) 