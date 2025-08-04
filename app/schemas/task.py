from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class TaskConfig(BaseModel):
    """任务配置模型"""
    enable_output: bool = True
    output_url: Optional[str] = None

class TaskCreate(BaseModel):
    """创建任务请求模型"""
    name: str
    description: Optional[str] = None
    stream_id: str
    algorithm_id: str
    enable_output: bool = True
    output_url: Optional[str] = None

class TaskStatus(BaseModel):
    """任务状态模型"""
    status: str
    details: Dict[str, Any] = {}

class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str
    name: str
    description: Optional[str] = None
    stream_id: str
    algorithm_id: str
    status: str
    config: Optional[str] = None
    runtime_status: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True 