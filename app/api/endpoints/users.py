from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserInfo, UserListData, PaginatingParams, UserListItem
from app.utils.utils import get_current_user, get_current_active_superuser

router = APIRouter()


@router.get("/info", response_model=UserInfo)
async def get_user_info(
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取当前用户信息
    """
    # 根据角色设置按钮权限
    buttons = []
    if current_user.role == "R_SUPER":
        buttons = ["B_CODE1", "B_CODE2", "B_CODE3"]
    elif current_user.role == "R_ADMIN":
        buttons = ["B_CODE1", "B_CODE2"]
    else:
        buttons = ["B_CODE1"]
        
    return {
        "userId": current_user.user_id,
        "userName": current_user.username,
        "roles": [current_user.role],
        "buttons": buttons,
        "avatar": current_user.avatar,
        "email": current_user.email
    }


@router.get("/list", response_model=UserListData)
async def get_user_list(
    params: PaginatingParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_superuser),
) -> Any:
    """
    获取用户列表（管理员权限）
    """
    # 基本查询
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    # 关键词搜索
    if params.keyword:
        search_filter = or_(
            User.username.ilike(f"%{params.keyword}%"),
            User.email.ilike(f"%{params.keyword}%"),
            User.fullname.ilike(f"%{params.keyword}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    # 计算总数
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 分页查询
    query = query.offset((params.current - 1) * params.size).limit(params.size)
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 构造符合前端格式的响应
    user_items = []
    for user in users:
        user_items.append(UserListItem(
            id=user.id,
            avatar=user.avatar or "",
            createBy="admin",
            createTime=user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            updateBy="admin",
            updateTime=user.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            status="1" if user.is_active else "2",
            userName=user.username,
            userGender="男",  # 默认值，数据库中未存储
            nickName=user.fullname or user.username,
            userPhone="",  # 数据库中未存储
            userEmail=user.email,
            userRoles=[user.role]
        ))
    
    return {
        "records": user_items,
        "current": params.current,
        "size": params.size,
        "total": total
    } 