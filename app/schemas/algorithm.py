from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime

class AlgorithmBase(BaseModel):
    """算法基础模型"""
    name: str
    algorithm_type: str
    description: Optional[str] = None
    version: Optional[str] = None

class AlgorithmCreate(AlgorithmBase):
    """创建算法模型"""
    config: Dict[str, Any] = Field(default_factory=dict)
    path: Optional[str] = None  # 添加可选的path字段

class AlgorithmUpdate(BaseModel):
    """更新算法模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None

class AlgorithmInDB(AlgorithmBase):
    """数据库中的算法模型"""
    algo_id: str
    path: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AlgorithmResponse(AlgorithmBase):
    """算法响应模型"""
    algo_id: str
    path: str
    config: Dict[str, Any]
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AlgorithmItem(BaseModel):
    """算法列表项模型"""
    algo_id: str
    name: str
    algorithm_type: str
    description: Optional[str] = None
    version: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class AlgorithmList(BaseModel):
    """算法列表模型"""
    total: int
    items: List[AlgorithmItem]

    class Config:
        from_attributes = True 