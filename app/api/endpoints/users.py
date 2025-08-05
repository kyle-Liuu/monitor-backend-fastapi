from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserInfo, UserListData, PaginatingParams, UserListItem
from app.utils.utils import get_current_user

router = APIRouter()


@router.get("/info")
def get_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取当前用户信息
    """
    # 解析用户角色列表
    user_roles = current_user.role.split(",") if current_user.role else []
    
    # 根据角色设置按钮权限
    buttons = []
    if "R_SUPER" in user_roles:
        buttons = ["B_CODE1", "B_CODE2", "B_CODE3"]
    elif "R_ADMIN" in user_roles:
        buttons = ["B_CODE1", "B_CODE2"]
    else:
        buttons = ["B_CODE1"]
        
    return {
        "code": 200,
        "data": {
            "userId": current_user.id,
            "userName": current_user.username,
            "roles": user_roles,
            "buttons": buttons,
            "avatar": current_user.avatar,
            "email": current_user.email,
            "fullName": current_user.full_name,
            "mobile": current_user.mobile,
            "tags": current_user.tags.split(",") if current_user.tags else []
        },
        "msg": "获取用户信息成功"
    }


@router.get("/list")
def get_user_list(
    params: PaginatingParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取用户列表（管理员权限）
    """
    # 验证用户是否有权限访问
    if not current_user.has_any_role(["R_SUPER", "R_ADMIN"]):
        raise HTTPException(status_code=403, detail="没有足够的权限")
    
    # 基本查询
    query = db.query(User)
    
    # 关键词搜索
    if params.keyword:
        search_filter = or_(
            User.username.ilike(f"%{params.keyword}%"),
            User.email.ilike(f"%{params.keyword}%"),
            User.full_name.ilike(f"%{params.keyword}%"),
            User.mobile.ilike(f"%{params.keyword}%")
        )
        query = query.filter(search_filter)
    
    # 角色过滤
    if params.role_filter:
        query = query.filter(User.role.ilike(f"%{params.role_filter}%"))
    
    # 状态过滤
    if params.status_filter is not None:
        query = query.filter(User.is_active == params.status_filter)
    
    # 计算总数
    total = query.count()
    
    # 分页查询
    users = query.offset((params.current - 1) * params.size).limit(params.size).all()
    
    # 构造符合前端格式的响应
    user_items = []
    for user in users:
        # 解析用户角色列表
        user_roles = user.role.split(",") if user.role else []
        # 解析用户标签列表
        user_tags = user.tags.split(",") if user.tags else []
        
        user_items.append(UserListItem(
            id=user.id,
            avatar=user.avatar or "",
            createBy="admin",
            createTime=user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else "",
            updateBy="admin",
            updateTime=user.updated_at.strftime("%Y-%m-%d %H:%M:%S") if user.updated_at else "",
            status="1" if user.is_active else "2",
            userName=user.username,
            userGender="男",  # 默认值，数据库中未存储
            nickName=user.full_name or user.username,
            userPhone=user.mobile or "",
            userEmail=user.email,
            userRoles=user_roles,
            userTags=user_tags
        ))
    
    return {
        "code": 200,
        "data": {
            "records": user_items,
            "current": params.current,
            "size": params.size,
            "total": total
        },
        "msg": "获取用户列表成功"
    } 