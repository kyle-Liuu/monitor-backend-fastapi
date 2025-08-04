"""
视频流管理相关的Pydantic模型定义
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class StreamType(str, Enum):
    """视频流类型枚举"""
    RTSP = "rtsp"
    RTMP = "rtmp"
    HTTP = "http"
    FILE = "file"


class StreamStatus(str, Enum):
    """视频流状态枚举"""
    INACTIVE = "inactive"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class StreamCreate(BaseModel):
    """创建视频流请求模型"""
    stream_id: Optional[str] = Field(None, description="视频流ID，不提供则自动生成")
    name: str = Field(..., min_length=1, max_length=100, description="视频流名称")
    url: str = Field(..., description="视频流地址")
    description: Optional[str] = Field("", max_length=500, description="视频流描述")
    stream_type: StreamType = Field(StreamType.RTSP, description="视频流类型")
    protocol: Optional[str] = Field("rtsp", description="协议类型：rtsp, GB28181, rtmp, hls")
    org_id: Optional[str] = Field(None, description="关联的组织ID")
    task_configs: Optional[List[dict]] = Field(None, description="任务配置列表（算法+配置）")
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if not v or len(v.strip()) < 10:
            raise ValueError('URL格式无效')
        return v.strip()
    
    class Config:
        extra = "forbid"  # 禁止额外字段，确保不接受旧的type字段


class StreamUpdate(BaseModel):
    """更新视频流请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="视频流名称")
    url: Optional[str] = Field(None, description="视频流地址")
    description: Optional[str] = Field(None, max_length=500, description="视频流描述")
    protocol: Optional[str] = Field(None, description="协议类型")
    org_id: Optional[str] = Field(None, description="关联的组织ID")
    description: Optional[str] = Field(None, max_length=500, description="视频流描述")
    stream_type: Optional[StreamType] = Field(None, description="视频流类型")
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if v is not None and (not v or len(v.strip()) < 10):
            raise ValueError('URL格式无效')
        return v.strip() if v else v
    
    class Config:
        extra = "forbid"  # 禁止额外字段，确保不接受旧的type字段


class StreamInfo(BaseModel):
    """视频流信息响应模型"""
    stream_id: str = Field(..., description="视频流ID")
    name: str = Field(..., description="视频流名称")
    url: str = Field(..., description="视频流地址")
    description: Optional[str] = Field(None, description="视频流描述")
    stream_type: StreamType = Field(..., description="视频流类型")
    status: StreamStatus = Field(..., description="视频流状态")
    is_forwarding: bool = Field(False, description="是否正在转发")
    frame_width: Optional[int] = Field(None, description="帧宽度")
    frame_height: Optional[int] = Field(None, description="帧高度")
    fps: Optional[float] = Field(None, description="帧率")
    consumer_count: int = Field(0, description="消费者数量")
    last_frame_time: Optional[datetime] = Field(None, description="最后一帧时间")
    last_online_time: Optional[datetime] = Field(None, description="最后在线时间")
    frame_count: int = Field(0, description="处理帧数")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    class Config:
        from_attributes = True


class StreamStats(BaseModel):
    """视频流统计信息"""
    stream_id: str = Field(..., description="视频流ID")
    fps: Optional[float] = Field(None, description="帧率")
    resolution: Optional[str] = Field(None, description="分辨率")
    bitrate: Optional[int] = Field(None, description="比特率")
    frame_count: int = Field(0, description="已处理帧数")
    error_count: int = Field(0, description="错误次数")
    last_error: Optional[str] = Field(None, description="最后错误信息")
    uptime_seconds: int = Field(0, description="运行时间(秒)")


class StreamTest(BaseModel):
    """视频流连接测试请求"""
    url: str = Field(..., description="要测试的视频流地址")
    timeout: int = Field(10, ge=1, le=30, description="超时时间(秒)")
    
    @validator('url')
    def validate_url(cls, v):
        """验证URL格式"""
        if not v or len(v.strip()) < 10:
            raise ValueError('URL格式无效')
        return v.strip()


class StreamTestResult(BaseModel):
    """视频流连接测试结果"""
    success: bool = Field(..., description="测试是否成功")
    url: str = Field(..., description="测试的URL")
    response_time: Optional[float] = Field(None, description="响应时间(秒)")
    resolution: Optional[str] = Field(None, description="视频分辨率")
    fps: Optional[float] = Field(None, description="帧率")
    codec: Optional[str] = Field(None, description="编码格式")
    error_message: Optional[str] = Field(None, description="错误信息")


class StreamSnapshot(BaseModel):
    """视频流截图响应"""
    stream_id: str = Field(..., description="视频流ID")
    snapshot_url: str = Field(..., description="截图URL")
    timestamp: datetime = Field(..., description="截图时间")
    format: str = Field("jpeg", description="图片格式")
    size: Optional[int] = Field(None, description="文件大小(字节)")


class StreamListResponse(BaseModel):
    """视频流列表响应"""
    total: int = Field(..., description="总数量")
    items: List[StreamInfo] = Field(..., description="视频流列表")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")


class StreamOperationResponse(BaseModel):
    """视频流操作响应"""
    success: bool = Field(..., description="操作是否成功")
    stream_id: str = Field(..., description="视频流ID")
    operation: str = Field(..., description="操作类型")
    message: str = Field(..., description="操作结果信息")
    data: Optional[Dict[str, Any]] = Field(None, description="附加数据")


# 视频流转发操作
class StreamForwardRequest(BaseModel):
    """视频流转发请求"""
    stream_id: str = Field(..., description="视频流ID")
    forward_config: Optional[dict] = Field(None, description="转发配置")


class StreamForwardResponse(BaseModel):
    """视频流转发响应"""
    success: bool
    stream_id: str
    is_forwarding: bool
    forward_url: Optional[str] = None
    message: str


# 视频流任务创建
class StreamTaskCreateRequest(BaseModel):
    """视频流任务创建请求"""
    stream_id: str = Field(..., description="视频流ID")
    algorithm_configs: List[dict] = Field(..., min_items=1, description="算法配置列表")


class StreamTaskCreateResponse(BaseModel):
    """视频流任务创建响应"""
    success: bool
    stream_id: str
    created_tasks: List[str]  # 创建的任务ID列表
    failed_tasks: List[dict]  # 失败的任务配置
    message: str


# 视频流组织绑定
class StreamOrgBindingRequest(BaseModel):
    """视频流组织绑定请求"""
    stream_id: str = Field(..., description="视频流ID")
    org_id: str = Field(..., description="组织ID")


class StreamOrgBindingResponse(BaseModel):
    """视频流组织绑定响应"""
    success: bool
    binding_id: str
    stream_id: str
    org_id: str
    message: str


# 扩展的视频流信息（包含组织和任务）
class StreamDetailInfo(BaseModel):
    """视频流详细信息"""
    stream_id: str
    name: str
    url: str
    description: Optional[str] = None
    stream_type: str
    protocol: str
    status: str
    is_forwarding: bool
    org_id: Optional[str] = None
    org_name: Optional[str] = None
    task_count: int = 0
    running_task_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 基础响应模型
class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = Field(200, description="响应状态码")
    message: str = Field("success", description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间") 