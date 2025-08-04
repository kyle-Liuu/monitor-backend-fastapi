from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from pydantic import ValidationError

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_password, ALGORITHM
from app.db.database import get_db
from app.db.models import User, BlacklistedToken
from app.schemas.auth import LoginParams, LoginResponse, TokenPayload, RefreshTokenResponse, Token
from app.utils.logger import user_logger
from app.utils.utils import get_current_user, oauth2_scheme

router = APIRouter()


@router.post("/login/OAuth2")
def login_form(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Dict:
    """
    用户表单登录接口 (Swagger UI使用)
    """
    client_ip = request.client.host if request.client else "unknown"
    
    username = form_data.username
    password = form_data.password
    
    # 记录登录尝试
    user_logger.info(f"用户尝试表单登录: {username} - 来自: {client_ip}")
    
    # 查询用户
    user = db.query(User).filter(User.username == username).first()
    
    # 用户不存在或密码错误
    if not user:
        user_logger.warning(f"登录失败: 用户不存在 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if not verify_password(password, user.hashed_password):
        user_logger.warning(f"登录失败: 密码错误 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 用户未激活
    if not user.is_active:
        user_logger.warning(f"登录失败: 账户未激活 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=403, detail="用户未激活")
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 添加额外信息到token
    extra_data = {"role": user.role, "username": user.username}
    token = create_access_token(
        subject=user.id, expires_delta=access_token_expires, extra_data=extra_data
    )
    
    # 生成刷新令牌
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )
    
    # 记录成功登录
    user_logger.info(f"用户表单登录成功: {username} - 角色: {user.role} - 来自: {client_ip}")
    
    # OAuth2要求返回的必须是以下格式，否则Swagger无法正确处理
    return {
        "access_token": token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }


@router.post("/login")
def login_json(
    request: Request,
    login_data: LoginParams,
    db: Session = Depends(get_db),
) -> Dict:
    """
    用户JSON登录接口 (前端应用使用)
    """
    client_ip = request.client.host if request.client else "unknown"
    
    username = login_data.userName
    password = login_data.password
    
    # 记录登录尝试
    user_logger.info(f"用户尝试JSON登录: {username} - 来自: {client_ip}")
    
    # 查询用户
    user = db.query(User).filter(User.username == username).first()
    
    # 用户不存在或密码错误
    if not user:
        user_logger.warning(f"登录失败: 用户不存在 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if not verify_password(password, user.hashed_password):
        user_logger.warning(f"登录失败: 密码错误 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 用户未激活
    if not user.is_active:
        user_logger.warning(f"登录失败: 账户未激活 {username} - 来自: {client_ip}")
        raise HTTPException(status_code=403, detail="用户未激活")
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # 添加额外信息到token
    extra_data = {"role": user.role, "username": user.username}
    token = create_access_token(
        subject=user.id, expires_delta=access_token_expires, extra_data=extra_data
    )
    
    # 生成刷新令牌
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )
    
    # 记录成功登录
    user_logger.info(f"用户JSON登录成功: {username} - 角色: {user.role} - 来自: {client_ip}")
    
    # 根据角色设置按钮权限
    buttons = []
    if user.role == "super":
        buttons = ["B_CODE1", "B_CODE2", "B_CODE3"]
    elif user.role == "admin":
        buttons = ["B_CODE1", "B_CODE2"]
    else:
        buttons = ["B_CODE1"]
    
    # 返回前端应用格式 - 按照前端期望的格式返回
    return {
        "code": 200,
        "data": {
        "token": token,
        "refreshToken": refresh_token
        },
        "msg": "登录成功"
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
) -> Any:
    """
    刷新令牌
    """
    try:
        # 解析令牌
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        
        # 验证是否为刷新令牌
        if not token_data.refresh:
            raise HTTPException(status_code=400, detail="无效的刷新令牌")
            
    except (JWTError, ValidationError):
        raise HTTPException(status_code=403, detail="无效的令牌")
    
    # 检查令牌是否在黑名单中
    blacklisted = db.query(BlacklistedToken).filter(BlacklistedToken.token == refresh_token).first()
    if blacklisted:
        raise HTTPException(status_code=403, detail="令牌已失效")
    
    # 查询用户
    user = db.query(User).filter(User.id == token_data.sub).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户未激活")
    
    # 生成新的访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    extra_data = {"role": user.role, "username": user.username}
    new_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires, extra_data=extra_data
    )
    
    # 生成新的刷新令牌
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    new_refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )
    
    # 将旧的刷新令牌加入黑名单
    db_token = BlacklistedToken(token=refresh_token)
    db.add(db_token)
    db.commit()
    
    user_logger.info(f"用户刷新令牌: {user.username}")
    
    return {
        "code": 200,
        "msg": "刷新令牌成功",
        "token": new_token,
        "refreshToken": new_refresh_token
    }


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Any:
    """
    用户登出接口
    """
    try:
        # 将当前令牌加入黑名单
        db_token = BlacklistedToken(token=token)
        db.add(db_token)
        db.commit()
        
        user_logger.info(f"用户登出: {current_user.username}")
        
        return {
            "code": 200,
            "msg": "登出成功"
        }
    except Exception as e:
        user_logger.error(f"用户登出失败: {current_user.username}, 错误: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="登出失败，请稍后重试")