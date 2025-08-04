import os
from pathlib import Path
import yaml
import secrets
from typing import List, Dict, Any, Optional

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent.absolute()

# 默认配置
DEFAULT_CONFIG = {
    "api": {
        "host": "0.0.0.0",
        "port": 8001,
        "cors_origins": ["*"],
        "token_expire_minutes": 60 * 24 * 8  # 8 days
    },
    "database": {
        "path": str(BASE_DIR / "app.db")
    },
    "redis": {
        "enabled": False,
        "host": "localhost",
        "port": 6379,
        "db": 0
    },
    "algorithms": {
        "base_path": str(BASE_DIR / "algorithms"),
        "uploads_path": str(BASE_DIR / "algorithms" / "uploads"),
        "installed_path": str(BASE_DIR / "algorithms" / "installed"),
        "registry_path": str(BASE_DIR / "algorithms" / "registry"),
        "max_instances_per_type": 2
    },
    "shared_memory": {
        "max_slots": 200,
        "frame_width": 1920,
        "frame_height": 1080,
        "channels": 3,
        "dynamic_adjustment": True
    },
    "ffmpeg": {
        "bin": "ffmpeg",
        "rtsp_output_base": "rtsp://localhost:8554/live",
        "options": {
            "preset": "ultrafast",
            "tune": "zerolatency"
        }
    },
    "streams": {
        "max_streams": 50,
        "frame_buffer_size": 10,
        "retry_interval": 5,
        "frame_skip": {
            "default": 3,
            "dynamic_adjustment": True
        }
    },
    "resources": {
        "max_cpu_percent": 90,
        "max_memory_percent": 90,
        "max_gpu_percent": 90,
        "enable_resource_control": True
    },
    "logging": {
        "level": "INFO",
        "file": str(BASE_DIR / "logs" / "app.log"),
        "max_size": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5
    }
}

# 加载配置文件
def load_config() -> Dict[str, Any]:
    """加载配置文件，如果不存在则创建默认配置"""
    config_path = BASE_DIR / "config.yaml"
    config = DEFAULT_CONFIG.copy()
    
    try:
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                
                # 验证配置文件
                if not isinstance(loaded_config, dict):
                    print(f"配置文件格式错误: {config_path}")
                    return config
                
                # 递归合并配置
                def merge_config(target, source):
                    for key, value in source.items():
                        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                            merge_config(target[key], value)
                        else:
                            target[key] = value
                
                merge_config(config, loaded_config)
            print(f"配置已从 {config_path} 加载")
        else:
            # 保存默认配置
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            print(f"默认配置已保存到 {config_path}")
    except Exception as e:
        print(f"加载配置失败: {e}")
    
    # 确保目录存在
    os.makedirs(config["algorithms"]["uploads_path"], exist_ok=True)
    os.makedirs(config["algorithms"]["installed_path"], exist_ok=True)
    os.makedirs(config["algorithms"]["registry_path"], exist_ok=True)
    os.makedirs(os.path.dirname(config["logging"]["file"]), exist_ok=True)
    
    return config

# 全局配置
CONFIG = load_config()

# API设置
API_HOST = CONFIG["api"]["host"]
API_PORT = CONFIG["api"]["port"]
CORS_ORIGINS = CONFIG["api"]["cors_origins"]
TOKEN_EXPIRE_MINUTES = CONFIG["api"]["token_expire_minutes"]

# 数据库设置
DATABASE_PATH = CONFIG["database"]["path"]

# Redis设置
REDIS_ENABLED = CONFIG["redis"]["enabled"]
REDIS_HOST = CONFIG["redis"]["host"]
REDIS_PORT = CONFIG["redis"]["port"]
REDIS_DB = CONFIG["redis"]["db"]

# 算法设置
ALGORITHMS_BASE_PATH = CONFIG["algorithms"]["base_path"]
ALGORITHMS_UPLOADS_PATH = CONFIG["algorithms"]["uploads_path"]
ALGORITHMS_INSTALLED_PATH = CONFIG["algorithms"]["installed_path"]
ALGORITHMS_REGISTRY_PATH = CONFIG["algorithms"]["registry_path"]
MAX_INSTANCES_PER_TYPE = CONFIG["algorithms"]["max_instances_per_type"]

# 共享内存设置
SHARED_MEMORY_MAX_SLOTS = CONFIG["shared_memory"]["max_slots"]
SHARED_MEMORY_FRAME_WIDTH = CONFIG["shared_memory"]["frame_width"]
SHARED_MEMORY_FRAME_HEIGHT = CONFIG["shared_memory"]["frame_height"]
SHARED_MEMORY_CHANNELS = CONFIG["shared_memory"]["channels"]
SHARED_MEMORY_DYNAMIC_ADJUSTMENT = CONFIG["shared_memory"]["dynamic_adjustment"]

# FFMPEG设置
FFMPEG_BIN = CONFIG["ffmpeg"]["bin"]
RTSP_OUTPUT_BASE = CONFIG["ffmpeg"]["rtsp_output_base"]
FFMPEG_OPTIONS = CONFIG["ffmpeg"]["options"]

# 流设置
MAX_STREAMS = CONFIG["streams"]["max_streams"]
FRAME_BUFFER_SIZE = CONFIG["streams"]["frame_buffer_size"]
RETRY_INTERVAL = CONFIG["streams"]["retry_interval"]
DEFAULT_FRAME_SKIP = CONFIG["streams"]["frame_skip"]["default"]
DYNAMIC_FRAME_SKIP = CONFIG["streams"]["frame_skip"]["dynamic_adjustment"]

# 资源设置
MAX_CPU_PERCENT = CONFIG["resources"]["max_cpu_percent"]
MAX_MEMORY_PERCENT = CONFIG["resources"]["max_memory_percent"]
MAX_GPU_PERCENT = CONFIG["resources"]["max_gpu_percent"]
ENABLE_RESOURCE_CONTROL = CONFIG["resources"]["enable_resource_control"]

# 日志设置
LOG_LEVEL = CONFIG["logging"]["level"]
LOG_FILE = CONFIG["logging"]["file"]
LOG_MAX_SIZE = CONFIG["logging"]["max_size"]
LOG_BACKUP_COUNT = CONFIG["logging"]["backup_count"]

# 密钥
SECRET_KEY = os.environ.get("SECRET_KEY") or "YRRcJZXdKQV12MOZi7GQDOYYXdkQQjk58amh5F6WEhA"

# 添加Settings类，用于兼容需要settings对象的代码
class Settings:
    """应用设置类"""
    
    def __init__(self):
        # 项目基本信息
        self.PROJECT_NAME = "AI智能监控系统"
        self.PROJECT_DESCRIPTION = "AI智能监控和视频行为分析系统API"
        self.PROJECT_VERSION = "1.0.0"
        self.API_VERSION = "1.0.0"
        self.API_V1_STR = "/api"
        self.API_PREFIX = "/api"
        self.DOCS_URL = "/docs"
        self.REDOC_URL = "/redoc"
        self.BACKEND_CORS_ORIGINS = CORS_ORIGINS
        
        # API设置
        self.HOST = API_HOST
        self.PORT = API_PORT
        self.CORS_ORIGINS = CORS_ORIGINS
        self.ACCESS_TOKEN_EXPIRE_MINUTES = TOKEN_EXPIRE_MINUTES
        self.REFRESH_TOKEN_EXPIRE_MINUTES = TOKEN_EXPIRE_MINUTES * 2  # 刷新令牌有效期是访问令牌的两倍
        
        # 数据库设置
        self.DATABASE_PATH = DATABASE_PATH
        # 添加SQLite异步URL
        self.SQLITE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"
        
        # Redis设置
        self.REDIS_ENABLED = REDIS_ENABLED
        self.REDIS_HOST = REDIS_HOST
        self.REDIS_PORT = REDIS_PORT
        self.REDIS_DB = REDIS_DB
        
        # 算法设置
        self.ALGORITHMS_BASE_PATH = ALGORITHMS_BASE_PATH
        self.ALGORITHMS_UPLOADS_PATH = ALGORITHMS_UPLOADS_PATH
        self.ALGORITHMS_INSTALLED_PATH = ALGORITHMS_INSTALLED_PATH
        self.ALGORITHMS_REGISTRY_PATH = ALGORITHMS_REGISTRY_PATH
        self.MAX_INSTANCES_PER_TYPE = MAX_INSTANCES_PER_TYPE
        
        # 共享内存设置
        self.SHARED_MEMORY_MAX_SLOTS = SHARED_MEMORY_MAX_SLOTS
        self.SHARED_MEMORY_FRAME_WIDTH = SHARED_MEMORY_FRAME_WIDTH
        self.SHARED_MEMORY_FRAME_HEIGHT = SHARED_MEMORY_FRAME_HEIGHT
        self.SHARED_MEMORY_CHANNELS = SHARED_MEMORY_CHANNELS
        self.SHARED_MEMORY_DYNAMIC_ADJUSTMENT = SHARED_MEMORY_DYNAMIC_ADJUSTMENT
        
        # FFMPEG设置
        self.FFMPEG_BIN = FFMPEG_BIN
        self.RTSP_OUTPUT_BASE = RTSP_OUTPUT_BASE
        self.FFMPEG_OPTIONS = FFMPEG_OPTIONS
        
        # 流设置
        self.MAX_STREAMS = MAX_STREAMS
        self.FRAME_BUFFER_SIZE = FRAME_BUFFER_SIZE
        self.RETRY_INTERVAL = RETRY_INTERVAL
        self.DEFAULT_FRAME_SKIP = DEFAULT_FRAME_SKIP
        self.DYNAMIC_FRAME_SKIP = DYNAMIC_FRAME_SKIP
        
        # 资源设置
        self.MAX_CPU_PERCENT = MAX_CPU_PERCENT
        self.MAX_MEMORY_PERCENT = MAX_MEMORY_PERCENT
        self.MAX_GPU_PERCENT = MAX_GPU_PERCENT
        self.ENABLE_RESOURCE_CONTROL = ENABLE_RESOURCE_CONTROL
        
        # 日志设置
        self.LOG_LEVEL = LOG_LEVEL
        self.LOG_FILE = LOG_FILE
        self.LOG_MAX_SIZE = LOG_MAX_SIZE
        self.LOG_BACKUP_COUNT = LOG_BACKUP_COUNT
        
        # 密钥
        self.SECRET_KEY = SECRET_KEY

# 创建settings实例
settings = Settings() 