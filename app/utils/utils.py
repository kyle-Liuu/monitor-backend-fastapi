from typing import Optional, Dict, Any
import random
import string
from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.database import get_db
from app.db.models import User, BlacklistedToken
from app.schemas.auth import TokenPayload

# OAuth2密码承载令牌
# 注意：tokenUrl必须与实际登录路径匹配，包括API前缀
# 在Swagger UI中，这个URL是相对于docs页面的
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/OAuth2")


def generate_unique_id(prefix: str, length: int = 7) -> str:
    """
    生成唯一标识，格式为前缀+指定长度的随机字母和数字
    
    Args:
        prefix: 标识前缀，如'user'、'menu'等
        length: 随机字符串长度，默认为7
    
    Returns:
        str: 生成的唯一标识
    """
    chars = string.ascii_letters + string.digits  # 字母和数字
    random_str = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}{random_str}"


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    获取当前用户
    """
    try:
        # 解析令牌
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法验证凭据",
        )
    
    # 检查token是否在黑名单中
    query = await db.execute(
        BlacklistedToken.__table__.select().where(BlacklistedToken.token == token)
    )
    if query.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="令牌已失效",
        )
    
    # 查询用户
    query = await db.execute(User.__table__.select().where(User.user_id == token_data.sub))
    user = query.fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户未激活")
    
    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前超级管理员用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="没有足够的权限"
        )
    return current_user 