"""
安全模块
处理密码加密和JWT令牌相关功能
"""

import secrets
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Union

import bcrypt
from jose import jwt

# 密码相关配置
SALT_ROUNDS = 12

# JWT相关配置
# 使用环境变量或固定密钥，确保整个应用使用相同密钥
SECRET_KEY = os.environ.get("SECRET_KEY") or "YRRcJZXdKQV12MOZi7GQDOYYXdkQQjk58amh5F6WEhA"  # 提供一个固定密钥作为默认值
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天


def get_password_hash(password: str) -> str:
    """
    对密码进行哈希加密
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=SALT_ROUNDS)
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[dict] = None
) -> str:
    """
    创建JWT访问令牌
    
    Args:
        subject: 令牌主题，通常为用户ID
        expires_delta: 令牌过期时间
        extra_data: 要添加到令牌的额外数据
    """
    to_encode = {"sub": subject}
    
    if extra_data:
        to_encode.update(extra_data)
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建JWT刷新令牌，有效期更长
    
    Args:
        subject: 令牌主题，通常为用户ID
        expires_delta: 令牌过期时间
    """
    to_encode = {"sub": subject}
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "refresh": True})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 