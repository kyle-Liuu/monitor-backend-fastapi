"""
组织管理相关的Pydantic模型定义
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    """组织基础信息"""
    name: str = Field(..., min_length=1, max_length=100, description="组织名称")
    parent_id: Optional[str] = Field(None, description="父级组织ID")
    description: Optional[str] = Field(None, max_length=500, description="组织描述")
    status: str = Field("active", description="组织状态：active, inactive")
    sort_order: int = Field(0, description="排序顺序")


class OrganizationCreate(OrganizationBase):
    """创建组织时的数据"""
    pass


class OrganizationUpdate(BaseModel):
    """更新组织时的数据"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="组织名称")
    description: Optional[str] = Field(None, max_length=500, description="组织描述")
    status: Optional[str] = Field(None, description="组织状态")
    sort_order: Optional[int] = Field(None, description="排序顺序")


class OrganizationInfo(BaseModel):
    """组织详细信息"""
    org_id: str
    name: str
    parent_id: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    status: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationNode(BaseModel):
    """组织树节点"""
    org_id: str
    name: str
    parent_id: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    status: str
    sort_order: int
    created_at: str
    stream_count: int = 0  # 绑定的视频流数量
    children: Optional[List['OrganizationNode']] = []

    class Config:
        from_attributes = True


class OrganizationTreeResponse(BaseModel):
    """组织树响应"""
    organizations: List[OrganizationNode]
    total: int


class OrganizationListItem(BaseModel):
    """组织列表项"""
    org_id: str
    name: str
    parent_id: Optional[str] = None
    parent_name: Optional[str] = None
    description: Optional[str] = None
    status: str
    sort_order: int
    stream_count: int = 0
    created_at: str

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """组织列表响应"""
    organizations: List[OrganizationListItem]
    total: int
    current: int = 1
    size: int = 20


class OrganizationOperationResponse(BaseModel):
    """组织操作响应"""
    success: bool
    org_id: str
    operation: str  # create, update, delete, move
    message: str
    data: Optional[dict] = None


# 组织移动操作
class OrganizationMoveRequest(BaseModel):
    """组织移动请求"""
    org_id: str = Field(..., description="要移动的组织ID")
    new_parent_id: Optional[str] = Field(None, description="新的父组织ID，null表示移动到根级别")
    update_children_path: bool = Field(True, description="是否更新子组织路径")


# 组织绑定相关Schema
class OrganizationBindingBase(BaseModel):
    """组织绑定基础信息"""
    org_id: str = Field(..., description="组织ID")
    stream_id: str = Field(..., description="视频流ID")


class OrganizationBindingCreate(OrganizationBindingBase):
    """创建组织绑定"""
    pass


class OrganizationBindingInfo(BaseModel):
    """组织绑定信息"""
    binding_id: str
    org_id: str
    stream_id: str
    org_name: Optional[str] = None
    stream_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationBindingListResponse(BaseModel):
    """组织绑定列表响应"""
    bindings: List[OrganizationBindingInfo]
    total: int


class OrganizationBindingBatchRequest(BaseModel):
    """批量绑定请求"""
    org_id: str = Field(..., description="组织ID")
    stream_ids: List[str] = Field(..., min_items=1, description="视频流ID列表")


class OrganizationBindingBatchResponse(BaseModel):
    """批量绑定响应"""
    success: bool
    org_id: str
    processed_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


# 组织下的设备/流
class OrganizationStreamInfo(BaseModel):
    """组织下的视频流信息"""
    stream_id: str
    name: str
    url: str
    status: str
    is_forwarding: bool
    created_at: str

    class Config:
        from_attributes = True


class OrganizationStreamsResponse(BaseModel):
    """组织下的视频流响应"""
    org_id: str
    org_name: str
    streams: List[OrganizationStreamInfo]
    total: int


# 查询参数
class OrganizationQueryParams(BaseModel):
    """组织查询参数"""
    current: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    status: Optional[str] = Field(None, description="状态过滤")
    parent_id: Optional[str] = Field(None, description="父组织ID过滤")


# 虚拟组织相关
class VirtualOrganizationBase(BaseModel):
    """虚拟组织基础信息"""
    name: str = Field(..., min_length=1, max_length=100, description="虚拟组织名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")


class VirtualOrganizationCreate(VirtualOrganizationBase):
    """创建虚拟组织"""
    org_refs: Optional[List[dict]] = Field(None, description="关联的组织")
    stream_ids: Optional[List[str]] = Field(None, description="关联的视频流")


class VirtualOrganizationInfo(BaseModel):
    """虚拟组织信息"""
    virtual_org_id: str
    name: str
    description: Optional[str] = None
    org_count: int = 0
    stream_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VirtualOrganizationListResponse(BaseModel):
    """虚拟组织列表响应"""
    virtual_orgs: List[VirtualOrganizationInfo]
    total: int 