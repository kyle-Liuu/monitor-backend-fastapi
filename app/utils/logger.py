import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import time

# 日志级别
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# 默认日志格式
DEFAULT_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
# 简化的访问日志格式
ACCESS_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')


def setup_logger(
    name: str = 'app',
    log_level: str = 'info',
    log_format: str = DEFAULT_LOG_FORMAT,
    log_to_console: bool = True,
    log_to_file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    use_time_rotating: bool = False,
    console_level: str = None  # 控制台日志级别，默认与log_level相同
):
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_level: 日志级别，可选值：debug, info, warning, error, critical
        log_format: 日志格式
        log_to_console: 是否输出到控制台
        log_to_file: 是否输出到文件
        max_bytes: 单个日志文件最大大小（字节）
        backup_count: 备份文件数量
        use_time_rotating: 是否使用时间轮转日志
        console_level: 控制台日志级别，可选值：debug, info, warning, error, critical
        
    Returns:
        配置好的日志记录器
    """
    # 创建日志目录
    if log_to_file and not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR)
        except Exception as e:
            print(f"创建日志目录失败: {e}")
            log_to_file = False
    
    # 获取日志级别
    level = LOG_LEVELS.get(log_level.lower(), logging.INFO)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 清除现有处理器
    if logger.handlers:
        logger.handlers = []
    
    # 创建日志格式化器
    formatter = logging.Formatter(log_format)
    
    # 添加控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        # 控制台日志级别可以单独设置
        if console_level:
            console_level_value = LOG_LEVELS.get(console_level.lower(), level)
            console_handler.setLevel(console_level_value)
        else:
            console_handler.setLevel(level)
        logger.addHandler(console_handler)
    
    # 添加文件处理器
    if log_to_file:
        log_file = os.path.join(LOG_DIR, f'{name}.log')
        
        if use_time_rotating:
            # 使用时间轮转处理器，每天轮转一次
            file_handler = TimedRotatingFileHandler(
                log_file, when='midnight', interval=1,
                backupCount=backup_count, encoding='utf-8'
            )
        else:
            # 使用大小轮转处理器
            file_handler = RotatingFileHandler(
                log_file, maxBytes=max_bytes,
                backupCount=backup_count, encoding='utf-8'
            )
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    
    return logger


# 默认应用日志记录器 - 控制台只显示警告及以上级别
app_logger = setup_logger(name='app', log_level='info', console_level='warning')

# API访问日志记录器 - 使用简化格式，控制台不显示访问日志
access_logger = setup_logger(
    name='access', 
    log_level='info',
    log_format=ACCESS_LOG_FORMAT,
    console_level='warning'
)

# 数据库操作日志记录器 - 设置为warning级别，减少SQL日志
db_logger = setup_logger(
    name='db', 
    log_level='warning', 
    use_time_rotating=True,
    console_level='error'  # 控制台只显示错误
)

# 用户操作日志记录器
user_logger = setup_logger(name='user', log_level='info', console_level='warning')


def get_logger(name: str = 'app'):
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
    
    Returns:
        日志记录器
    """
    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)
    return setup_logger(name=name)

# 设置第三方库的日志级别
logging.getLogger('uvicorn').setLevel(logging.WARNING)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
