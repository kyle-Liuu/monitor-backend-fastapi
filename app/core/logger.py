import logging
import logging.handlers
import os
import sys
from pathlib import Path
import traceback
from typing import Optional, Dict, Any, List

from .config import LOG_LEVEL, LOG_FILE, LOG_MAX_SIZE, LOG_BACKUP_COUNT

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# 确保日志目录存在
log_dir = os.path.dirname(LOG_FILE)
os.makedirs(log_dir, exist_ok=True)

# 创建日志格式化器
log_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s [%(processName)s:%(threadName)s] %(message)s'
)

# 创建文件处理器
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=LOG_MAX_SIZE,
    backupCount=LOG_BACKUP_COUNT,
    encoding='utf-8'
)
file_handler.setFormatter(log_formatter)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# 配置根日志器
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# 设置第三方库的日志级别
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """设置特定模块的日志器"""
    logger = logging.getLogger(name)
    if level:
        logger.setLevel(LOG_LEVELS.get(level, logging.INFO))
    return logger

def log_exception(exc: Exception, context: Dict[str, Any] = None) -> None:
    """记录异常详细信息"""
    tb_str = traceback.format_exception(type(exc), exc, exc.__traceback__)
    error_msg = f"异常: {str(exc)}\n{''.join(tb_str)}"
    
    if context:
        context_str = "\n".join(f"{k}: {v}" for k, v in context.items())
        error_msg = f"{error_msg}\n上下文:\n{context_str}"
    
    logging.error(error_msg)

class ErrorCollector:
    """错误收集器，用于收集和汇总错误"""
    
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
    
    def add_error(self, message: str, source: str = None, 
                 code: str = None, details: Any = None) -> None:
        """添加错误"""
        self.errors.append({
            "message": message,
            "source": source,
            "code": code,
            "details": details
        })
    
    def has_errors(self) -> bool:
        """检查是否有错误"""
        return len(self.errors) > 0
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """获取所有错误"""
        return self.errors.copy()
    
    def clear(self) -> None:
        """清除所有错误"""
        self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "has_errors": self.has_errors(),
            "error_count": len(self.errors),
            "errors": self.errors
        }

# 创建默认日志器
logger = setup_logger("app")

# 导出
__all__ = ["logger", "setup_logger", "log_exception", "ErrorCollector"] 