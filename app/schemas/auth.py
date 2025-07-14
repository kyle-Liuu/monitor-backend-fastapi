from typing import Optional, List

from pydantic import BaseModel


class Token(BaseModel):
    """
    令牌模型 (OAuth2兼容)
    """
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None


class TokenPayload(BaseModel):
    """
    令牌载荷
    """
    sub: Optional[str] = None
    exp: Optional[int] = None
    refresh: Optional[bool] = False
    role: Optional[str] = None
    username: Optional[str] = None


class LoginParams(BaseModel):
    """
    登录参数
    """
    userName: str
    password: str


class UserData(BaseModel):
    """
    用户数据
    """
    userId: str
    userName: str
    roles: List[str]
    buttons: List[str]


class LoginResponse(BaseModel):
    """
    登录响应
    """
    code: int = 200
    data: UserData
    msg: str = "登录成功"
    token: str
    refreshToken: str
    # OAuth2兼容字段
    access_token: str
    token_type: str = "bearer"
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """
    刷新令牌响应
    """
    code: int = 200
    msg: str = "刷新令牌成功"
    token: str
    refreshToken: str 