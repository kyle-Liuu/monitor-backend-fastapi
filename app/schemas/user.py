from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """
    用户基础信息
    """
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    is_active: bool = Field(True, description="是否激活")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    mobile: Optional[str] = Field(None, max_length=20, description="手机号")
    tags: Optional[str] = Field(None, max_length=500, description="标签列表，逗号分隔")


class UserCreate(UserBase):
    """
    创建用户时的数据
    """
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    role: str = Field("R_USER", description="角色列表，逗号分隔，如R_SUPER,R_ADMIN")


class UserUpdate(BaseModel):
    """
    更新用户时的数据
    """
    username: Optional[str] = Field(None, min_length=1, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    password: Optional[str] = Field(None, min_length=6, max_length=50, description="密码")
    full_name: Optional[str] = Field(None, max_length=100, description="全名")
    mobile: Optional[str] = Field(None, max_length=20, description="手机号")
    tags: Optional[str] = Field(None, max_length=500, description="标签列表")
    role: Optional[str] = Field(None, description="角色列表，逗号分隔")
    is_active: Optional[bool] = Field(None, description="是否激活")


class UserInfo(BaseModel):
    """
    用户信息，符合前端接口要求
    """
    userId: str
    userName: str
    roles: List[str]  # 从用户的role字段解析出的角色列表
    buttons: List[str]  # 基于角色计算的按钮权限
    avatar: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    fullName: Optional[str] = None
    tags: Optional[List[str]] = None  # 标签列表

    class Config:
        from_attributes = True


class UserDetailInfo(BaseModel):
    """
    用户详细信息
    """
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    mobile: Optional[str] = None
    tags: Optional[str] = None
    role: str  # 角色字符串，如"R_SUPER,R_ADMIN"
    roles: List[str]  # 解析后的角色列表
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatingParams(BaseModel):
    """
    分页查询参数
    """
    current: int = Field(1, ge=1, description="页码")
    size: int = Field(10, ge=1, le=100, description="每页数量")
    keyword: Optional[str] = Field(None, description="搜索关键词")
    role_filter: Optional[str] = Field(None, description="角色过滤")
    status_filter: Optional[bool] = Field(None, description="状态过滤")


class UserListItem(BaseModel):
    """
    用户列表项
    """
    id: str  # 用户ID
    avatar: str
    createBy: str
    createTime: str
    updateBy: str
    updateTime: str
    status: str  # '1': 激活, '2': 未激活
    userName: str
    userGender: str  # 暂时保留兼容性
    nickName: str
    userPhone: str
    userEmail: str
    userRoles: List[str]  # 角色列表
    userTags: Optional[List[str]] = []  # 标签列表

    class Config:
        from_attributes = True


class UserListData(BaseModel):
    """
    用户列表数据，符合前端接口要求
    """
    records: List[UserListItem]
    current: int
    size: int
    total: int 


class UserOperationResponse(BaseModel):
    """
    用户操作响应
    """
    success: bool
    user_id: str
    operation: str  # create, update, delete, activate, deactivate
    message: str
    data: Optional[dict] = None


class UserRoleUpdateRequest(BaseModel):
    """
    用户角色更新请求
    """
    user_id: str = Field(..., description="用户ID")
    roles: List[str] = Field(..., min_items=1, description="角色列表")


class UserBatchOperation(BaseModel):
    """
    用户批量操作
    """
    user_ids: List[str] = Field(..., min_items=1, description="用户ID列表")
    operation: str = Field(..., description="操作类型：activate, deactivate, delete")


class UserBatchResponse(BaseModel):
    """
    用户批量操作响应
    """
    success: bool
    operation: str
    processed_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class UserRoleStatistics(BaseModel):
    """
    用户角色统计
    """
    role_code: str
    role_name: str
    user_count: int


class UserStatisticsResponse(BaseModel):
    """
    用户统计响应
    """
    total_users: int
    active_users: int
    inactive_users: int
    role_statistics: List[UserRoleStatistics] 