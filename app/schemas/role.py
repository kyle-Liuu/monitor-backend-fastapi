"""
角色管理相关的Pydantic模型定义
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    """角色基础信息"""
    role_code: str = Field(..., min_length=1, max_length=50, description="角色编码，如R_SUPER")
    role_name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, max_length=500, description="角色描述")
    is_enabled: bool = Field(True, description="是否启用")


class RoleCreate(RoleBase):
    """创建角色时的数据"""
    pass


class RoleUpdate(BaseModel):
    """更新角色时的数据"""
    role_name: Optional[str] = Field(None, min_length=1, max_length=100, description="角色名称")
    description: Optional[str] = Field(None, max_length=500, description="角色描述")
    is_enabled: Optional[bool] = Field(None, description="是否启用")


class RoleInfo(BaseModel):
    """角色详细信息"""
    role_id: str
    role_code: str
    role_name: str
    description: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoleListItem(BaseModel):
    """角色列表项"""
    role_id: str
    role_code: str
    role_name: str
    description: Optional[str] = None
    is_enabled: bool
    user_count: int = 0  # 拥有该角色的用户数量
    created_at: str

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """角色列表响应"""
    roles: List[RoleListItem]
    total: int
    current: int = 1
    size: int = 20


class RoleOperationResponse(BaseModel):
    """角色操作响应"""
    success: bool
    role_id: str
    operation: str  # create, update, delete
    message: str
    data: Optional[dict] = None


# 分页查询参数
class RoleQueryParams(BaseModel):
    """角色查询参数"""
    current: int = Field(1, ge=1, description="页码")
    size: int = Field(20, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    is_enabled: Optional[bool] = Field(None, description="是否启用过滤")


# 批量操作
class RoleBatchOperation(BaseModel):
    """角色批量操作"""
    role_ids: List[str] = Field(..., min_items=1, description="角色ID列表")
    operation: str = Field(..., description="操作类型：enable, disable, delete")


class RoleBatchResponse(BaseModel):
    """角色批量操作响应"""
    success: bool
    operation: str
    processed_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None 