"""
分析器模块的Pydantic模型
- 定义与分析器相关的所有数据模型
- 用于请求验证和响应序列化
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

# 状态枚举
class StreamStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

class AlarmStatus(str, Enum):
    NEW = "new"
    PROCESSED = "processed"
    IGNORED = "ignored"

class AlarmSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class OutputType(str, Enum):
    RTMP = "rtmp"
    RTSP = "rtsp"
    HTTP = "http"
    FILE = "file"

# 基础模型
class BaseResponse(BaseModel):
    """API基础响应模型"""
    success: bool = True
    message: str = ""
    data: Optional[Any] = None

# 流模型
class StreamBase(BaseModel):
    """流基础信息"""
    url: str
    name: Optional[str] = None
    description: Optional[str] = None
    type: str = "rtsp"

class StreamCreate(StreamBase):
    """创建流请求"""
    stream_id: Optional[str] = None

class StreamInfo(StreamBase):
    """流详细信息"""
    stream_id: str
    status: StreamStatus
    error_message: Optional[str] = None
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    fps: Optional[float] = None
    consumer_count: int = 0
    last_frame_time: Optional[datetime] = None
    frame_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class StreamUpdate(BaseModel):
    """更新流请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    type: Optional[str] = None

# 任务模型
class TaskBase(BaseModel):
    """任务基础信息"""
    stream_id: str
    algorithm_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    alarm_config: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    """创建任务请求"""
    task_id: Optional[str] = None

class TaskInfo(TaskBase):
    """任务详细信息"""
    task_id: str
    name: str
    status: TaskStatus
    error_message: Optional[str] = None
    frame_count: int = 0
    last_frame_time: Optional[datetime] = None
    processing_time: float = 0.0
    detection_count: int = 0
    alarm_count: int = 0
    model_instance_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        protected_namespaces = ()

class TaskUpdate(BaseModel):
    """更新任务请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    alarm_config: Optional[Dict[str, Any]] = None

# 告警模型
class AlarmBase(BaseModel):
    """告警基础信息"""
    task_id: str
    alarm_type: str
    confidence: float
    bbox: Optional[List[float]] = None
    original_image: Optional[str] = None
    processed_image: Optional[str] = None
    video_clip: Optional[str] = None
    processed: bool = False
    severity: AlarmSeverity = AlarmSeverity.MEDIUM

class AlarmInfo(AlarmBase):
    """告警详细信息"""
    alarm_id: str
    created_at: datetime

class AlarmUpdate(BaseModel):
    """更新告警请求"""
    status: Optional[AlarmStatus] = None
    processed: Optional[bool] = None
    severity: Optional[AlarmSeverity] = None

# 算法模型
class AlgorithmInfo(BaseModel):
    """算法信息"""
    algorithm_id: str
    name: str
    description: Optional[str] = None
    package_name: str
    algorithm_type: str = "detection"
    version: str = "1.0.0"
    config: Optional[Dict[str, Any]] = None
    status: StreamStatus = StreamStatus.INACTIVE
    model_path: Optional[str] = None
    max_instances: int = 3
    current_instances: int = 0
    device_type: str = "cpu"
    memory_usage: Optional[float] = None
    inference_time: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        protected_namespaces = ()

# 模型实例模型
class ModelInstanceInfo(BaseModel):
    """模型实例信息"""
    instance_id: str
    algorithm_id: str
    instance_name: str
    status: str = "idle"  # idle, busy, error
    device_type: str = "cpu"
    memory_usage: Optional[float] = None
    load_time: Optional[datetime] = None
    last_used: Optional[datetime] = None
    use_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# 输出模型
class OutputBase(BaseModel):
    """输出基础信息"""
    task_id: str
    output_type: OutputType = OutputType.RTMP
    url: str
    config: Optional[Dict[str, Any]] = None

class OutputCreate(OutputBase):
    """创建输出请求"""
    output_id: Optional[str] = None

class OutputInfo(OutputBase):
    """输出详细信息"""
    output_id: str
    status: str
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# 分析器状态模型
class AnalyzerStatus(BaseModel):
    """分析器状态"""
    is_running: bool
    start_time: Optional[datetime] = None
    active_streams: int = 0
    active_tasks: int = 0
    cpu_usage: float = 0
    memory_usage: float = 0
    gpu_usage: Optional[float] = None
    frame_processed: int = 0
    events_processed: int = 0
    
    # 子模块状态
    stream_module: Dict[str, Any] = {}
    algorithm_module: Dict[str, Any] = {}
    task_module: Dict[str, Any] = {}
    event_bus: Dict[str, Any] = {}
    
    # 可能的错误
    errors: List[str] = []
    warnings: List[str] = []

# 系统配置模型
class SystemConfigInfo(BaseModel):
    """系统配置信息"""
    config_id: str
    config_key: str
    config_value: Optional[str] = None
    config_type: str = "string"
    description: Optional[str] = None
    is_system: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None 