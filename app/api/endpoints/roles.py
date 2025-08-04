"""
角色管理API端点
提供角色的完整CRUD操作和权限管理
"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db.database import get_db
from app.db.models import Role, User
from app.schemas.role import (
    RoleCreate, RoleUpdate, RoleInfo, RoleListResponse, 
    RoleOperationResponse, RoleQueryParams, RoleBatchOperation, RoleBatchResponse
)
from app.utils.utils import get_current_active_superuser, get_current_user, generate_unique_id

router = APIRouter()


@router.get("/list", response_model=RoleListResponse)
def get_roles_list(
    params: RoleQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取角色列表
    """
    # 用户有访问权限即可查看角色列表
    
    # 基本查询
    query = db.query(Role)
    
    # 关键词搜索
    if params.keyword:
        search_filter = or_(
            Role.role_name.ilike(f"%{params.keyword}%"),
            Role.role_code.ilike(f"%{params.keyword}%"),
            Role.description.ilike(f"%{params.keyword}%")
        )
        query = query.filter(search_filter)
    
    # 状态过滤
    if params.is_enabled is not None:
        query = query.filter(Role.is_enabled == params.is_enabled)
    
    # 计算总数
    total = query.count()
    
    # 分页查询
    roles = query.offset((params.current - 1) * params.size).limit(params.size).all()
    
    # 统计每个角色的用户数量
    role_items = []
    for role in roles:
        # 查询拥有该角色的用户数量
        user_count = db.query(User).filter(
            User.role.like(f"%{role.role_code}%")
        ).count()
        
        role_items.append({
            "role_id": role.role_id,
            "role_code": role.role_code,
            "role_name": role.role_name,
            "description": role.description,
            "is_enabled": role.is_enabled,
            "user_count": user_count,
            "created_at": role.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return RoleListResponse(
        roles=role_items,
        total=total,
        current=params.current,
        size=params.size
    )


@router.get("/{role_id}", response_model=RoleInfo)
def get_role_detail(
    role_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取角色详情
    """
    # 用户有访问权限即可查看角色详情
    
    role = db.query(Role).filter(Role.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    return role


@router.post("", response_model=RoleOperationResponse)
def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_superuser)
) -> Any:
    """
    创建新角色 - 仅超级管理员可操作
    """
    # 检查角色编码是否已存在
    existing = db.query(Role).filter(Role.role_code == role_data.role_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"角色编码已存在: {role_data.role_code}")
    
    # 生成唯一ID
    role_id = generate_unique_id("role")
    
    # 创建角色
    db_role = Role(
        role_id=role_id,
        role_code=role_data.role_code,
        role_name=role_data.role_name,
        description=role_data.description,
        is_enabled=role_data.is_enabled
    )
    
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    
    return RoleOperationResponse(
        success=True,
        role_id=role_id,
        operation="create",
        message="角色创建成功",
        data={"role_code": role_data.role_code, "role_name": role_data.role_name}
    )


@router.put("/{role_id}", response_model=RoleOperationResponse)
def update_role(
    role_id: str,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_superuser)
) -> Any:
    """
    更新角色信息 - 仅超级管理员可操作
    """
    role = db.query(Role).filter(Role.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 更新字段
    if role_data.role_name is not None:
        role.role_name = role_data.role_name
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.is_enabled is not None:
        role.is_enabled = role_data.is_enabled
    
    db.commit()
    
    return RoleOperationResponse(
        success=True,
        role_id=role_id,
        operation="update",
        message="角色更新成功"
    )


@router.delete("/{role_id}", response_model=RoleOperationResponse)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_superuser)
) -> Any:
    """
    删除角色 - 仅超级管理员可操作
    """
    role = db.query(Role).filter(Role.role_id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    # 检查是否有用户正在使用该角色
    users_with_role = db.query(User).filter(
        User.role.like(f"%{role.role_code}%")
    ).count()
    
    if users_with_role > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"无法删除角色，还有 {users_with_role} 个用户正在使用该角色"
        )
    
    # 检查是否为系统内置角色
    if role.role_code in ["R_SUPER", "R_ADMIN", "R_USER"]:
        raise HTTPException(status_code=400, detail="不能删除系统内置角色")
    
    db.delete(role)
    db.commit()
    
    return RoleOperationResponse(
        success=True,
        role_id=role_id,
        operation="delete",
        message="角色删除成功"
    )


@router.post("/batch", response_model=RoleBatchResponse)
def batch_role_operation(
    operation_data: RoleBatchOperation,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_superuser)
) -> Any:
    """
    批量角色操作 - 仅超级管理员可操作
    """
    processed_count = 0
    failed_count = 0
    details = []
    
    for role_id in operation_data.role_ids:
        try:
            role = db.query(Role).filter(Role.role_id == role_id).first()
            if not role:
                failed_count += 1
                details.append({"role_id": role_id, "error": "角色不存在"})
                continue
            
            if operation_data.operation == "enable":
                role.is_enabled = True
            elif operation_data.operation == "disable":
                role.is_enabled = False
            elif operation_data.operation == "delete":
                # 检查系统内置角色
                if role.role_code in ["R_SUPER", "R_ADMIN", "R_USER"]:
                    failed_count += 1
                    details.append({"role_id": role_id, "error": "不能删除系统内置角色"})
                    continue
                
                # 检查是否有用户使用
                users_count = db.query(User).filter(
                    User.role.like(f"%{role.role_code}%")
                ).count()
                if users_count > 0:
                    failed_count += 1
                    details.append({"role_id": role_id, "error": f"有{users_count}个用户正在使用"})
                    continue
                
                db.delete(role)
            else:
                failed_count += 1
                details.append({"role_id": role_id, "error": "不支持的操作类型"})
                continue
            
            processed_count += 1
            
        except Exception as e:
            failed_count += 1
            details.append({"role_id": role_id, "error": str(e)})
    
    db.commit()
    
    return RoleBatchResponse(
        success=failed_count == 0,
        operation=operation_data.operation,
        processed_count=processed_count,
        failed_count=failed_count,
        message=f"批量操作完成，成功{processed_count}个，失败{failed_count}个",
        details=details if failed_count > 0 else None
    )


@router.get("/code/{role_code}", response_model=RoleInfo)
def get_role_by_code(
    role_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    根据角色编码获取角色信息
    """
    # 用户有访问权限即可查看角色信息
    
    role = db.query(Role).filter(Role.role_code == role_code).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    
    return role 