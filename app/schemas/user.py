from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """
    用户基础信息
    """
    username: str
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    """
    创建用户时的数据
    """
    password: str
    fullname: Optional[str] = None


class UserUpdate(UserBase):
    """
    更新用户时的数据
    """
    password: Optional[str] = None
    fullname: Optional[str] = None


class UserInfo(BaseModel):
    """
    用户信息，符合前端接口要求
    """
    userId: str
    userName: str
    roles: List[str]
    buttons: List[str]
    avatar: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatingParams(BaseModel):
    """
    分页查询参数
    """
    current: int = 1
    size: int = 10
    keyword: Optional[str] = None


class UserListItem(BaseModel):
    """
    用户列表项
    """
    id: int
    avatar: str
    createBy: str
    createTime: str
    updateBy: str
    updateTime: str
    status: str  # '1': 在线, '2': 离线, '3': 异常, '4': 注销
    userName: str
    userGender: str
    nickName: str
    userPhone: str
    userEmail: str
    userRoles: List[str]


class UserListData(BaseModel):
    """
    用户列表数据，符合前端接口要求
    """
    records: List[UserListItem]
    current: int
    size: int
    total: int 