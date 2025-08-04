from typing import Optional, Dict, Any, Union, List
import random
import string
from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import ValidationError
import logging

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.database import get_db
from app.db.models import User, BlacklistedToken
from app.schemas.auth import TokenPayload

# 配置日志
logger = logging.getLogger(__name__)

# OAuth2密码承载令牌
# 注意：tokenUrl必须与实际登录路径匹配，包括API前缀
# 在Swagger UI中，这个URL是相对于docs页面的
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login/OAuth2")


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


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前用户
    """
    try:
        # 记录令牌信息，方便调试
        logger.info(f"正在验证令牌: {token[:10]}...")
        
        # 解析令牌
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        
        logger.info(f"令牌解析成功，用户ID: {token_data.sub}")
    except jwt.JWTError as e:
        # 记录具体的JWT错误
        logger.error(f"JWT解析错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法验证凭据",
        )
    except ValidationError as e:
        # 记录载荷验证错误
        logger.error(f"令牌载荷验证错误: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法验证凭据",
        )
    
    # 检查token是否在黑名单中
    blacklisted = db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
    if blacklisted:
        logger.warning(f"令牌已被列入黑名单: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="令牌已失效",
        )
    
    # 查询用户
    user = db.query(User).filter(User.id == token_data.sub).first()
    
    if not user:
        logger.error(f"未找到用户: {token_data.sub}")
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        logger.warning(f"用户未激活: {user.username}")
        raise HTTPException(status_code=403, detail="用户未激活")
    
    logger.info(f"用户认证成功: {user.username}")
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前激活用户
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=403, detail="用户未激活"
        )
    return current_user


def get_current_active_superuser(
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

# API响应辅助函数
def success_response(message: str = "操作成功", data: Union[Dict, List, Any, None] = None) -> Dict:
    """
    生成统一成功响应
    
    Args:
        message: 成功消息
        data: 响应数据
        
    Returns:
        统一格式的成功响应字典
    """
    return {
        "success": True,
        "message": message,
        "data": data
    }

def error_response(message: str = "操作失败", data: Union[Dict, List, Any, None] = None) -> Dict:
    """
    生成统一错误响应
    
    Args:
        message: 错误消息
        data: 响应数据
        
    Returns:
        统一格式的错误响应字典
    """
    return {
        "success": False,
        "message": message,
        "data": data
    } 