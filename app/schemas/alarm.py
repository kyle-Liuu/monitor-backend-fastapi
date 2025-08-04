"""
报警相关的Pydantic模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AlarmBase(BaseModel):
    """报警基础模型"""
    task_id: str = Field(..., description="任务ID")
    alarm_type: str = Field(..., description="报警类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    bbox: Optional[str] = Field(None, description="边界框JSON字符串")
    severity: str = Field(default="medium", description="严重程度")

class AlarmCreate(AlarmBase):
    """创建报警模型"""
    original_image: Optional[str] = Field(None, description="原始图片路径")
    processed_image: Optional[str] = Field(None, description="处理后图片路径")
    video_clip: Optional[str] = Field(None, description="视频片段路径")

class AlarmUpdate(BaseModel):
    """更新报警模型"""
    processed: Optional[bool] = Field(None, description="是否已处理")
    severity: Optional[str] = Field(None, description="严重程度")

class AlarmResponse(AlarmBase):
    """报警响应模型"""
    alarm_id: str = Field(..., description="报警ID")
    processed: bool = Field(default=False, description="是否已处理")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    original_image: Optional[str] = Field(None, description="原始图片路径")
    processed_image: Optional[str] = Field(None, description="处理后图片路径")
    video_clip: Optional[str] = Field(None, description="视频片段路径")

    class Config:
        from_attributes = True

class AlarmListResponse(BaseModel):
    """报警列表响应模型"""
    alarms: List[AlarmResponse] = Field(..., description="报警列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")

class AlarmVideoSaveRequest(BaseModel):
    """报警视频保存请求模型"""
    stream_id: str = Field(..., description="流ID")
    alarm_id: str = Field(..., description="报警ID")
    pre_seconds: int = Field(default=1, ge=0, le=10, description="前N秒")
    post_seconds: int = Field(default=1, ge=0, le=10, description="后N秒")

class AlarmVideoSaveResponse(BaseModel):
    """报警视频保存响应模型"""
    alarm_id: str = Field(..., description="报警ID")
    video_path: str = Field(..., description="视频路径")
    pre_seconds: int = Field(..., description="前N秒")
    post_seconds: int = Field(..., description="后N秒")
    saved_time: str = Field(..., description="保存时间")

class AlarmStatistics(BaseModel):
    """报警统计模型"""
    total_alarms: int = Field(..., description="总报警数")
    processed_alarms: int = Field(..., description="已处理报警数")
    unprocessed_alarms: int = Field(..., description="未处理报警数")
    high_severity: int = Field(..., description="高严重程度报警数")
    medium_severity: int = Field(..., description="中严重程度报警数")
    low_severity: int = Field(..., description="低严重程度报警数")
    today_alarms: int = Field(..., description="今日报警数")
    week_alarms: int = Field(..., description="本周报警数")
    month_alarms: int = Field(..., description="本月报警数") 