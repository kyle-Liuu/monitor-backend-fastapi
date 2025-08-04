"""
组织管理API端点
提供组织的完整CRUD操作、层级管理和绑定管理
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db.database import get_db
from app.db.models import Organization, OrganizationBinding, VideoStream
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationInfo, OrganizationNode,
    OrganizationTreeResponse, OrganizationListResponse, OrganizationOperationResponse,
    OrganizationMoveRequest, OrganizationQueryParams, OrganizationStreamsResponse
)
from app.utils.utils import get_current_user, get_current_active_superuser, generate_unique_id

router = APIRouter()


def build_organization_tree(organizations: List[Organization], parent_id: Optional[str] = None) -> List[OrganizationNode]:
    """构建组织树"""
    tree = []
    for org in organizations:
        if org.parent_id == parent_id:
            # 统计绑定的视频流数量
            stream_count = len(org.bindings) if hasattr(org, 'bindings') else 0
            
            node = OrganizationNode(
                org_id=org.org_id,
                name=org.name,
                parent_id=org.parent_id,
                path=org.path,
                description=org.description,
                status=org.status,
                sort_order=org.sort_order,
                created_at=org.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                stream_count=stream_count,
                children=build_organization_tree(organizations, org.org_id)
            )
            tree.append(node)
    
    # 按排序顺序排列
    tree.sort(key=lambda x: x.sort_order)
    return tree


def update_organization_path(db: Session, org: Organization, new_parent_id: Optional[str] = None):
    """更新组织路径"""
    if new_parent_id:
        parent = db.query(Organization).filter(Organization.org_id == new_parent_id).first()
        if parent:
            org.path = f"{parent.path}{org.org_id}/"
        else:
            org.path = f"/{org.org_id}/"
    else:
        org.path = f"/{org.org_id}/"
    
    org.parent_id = new_parent_id


@router.get("/tree", response_model=OrganizationTreeResponse)
def get_organization_tree(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取组织树结构
    """
    # 查询所有组织
    organizations = db.query(Organization).all()
    
    # 构建树结构
    tree = build_organization_tree(organizations)
    
    return OrganizationTreeResponse(
        organizations=tree,
        total=len(organizations)
    )


@router.get("/list", response_model=OrganizationListResponse)
def get_organizations_list(
    params: OrganizationQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取组织列表（平铺结构）
    """
    # 基本查询
    query = db.query(Organization)
    
    # 关键词搜索
    if params.keyword:
        search_filter = or_(
            Organization.name.ilike(f"%{params.keyword}%"),
            Organization.description.ilike(f"%{params.keyword}%")
        )
        query = query.filter(search_filter)
    
    # 状态过滤
    if params.status:
        query = query.filter(Organization.status == params.status)
    
    # 父组织过滤
    if params.parent_id:
        query = query.filter(Organization.parent_id == params.parent_id)
    
    # 计算总数
    total = query.count()
    
    # 分页查询
    organizations = query.order_by(Organization.sort_order).offset(
        (params.current - 1) * params.size
    ).limit(params.size).all()
    
    # 构造响应数据
    org_items = []
    for org in organizations:
        # 获取父组织名称
        parent_name = None
        if org.parent_id:
            parent = db.query(Organization).filter(Organization.org_id == org.parent_id).first()
            parent_name = parent.name if parent else None
        
        # 统计绑定的视频流数量
        stream_count = db.query(OrganizationBinding).filter(
            OrganizationBinding.org_id == org.org_id
        ).count()
        
        org_items.append({
            "org_id": org.org_id,
            "name": org.name,
            "parent_id": org.parent_id,
            "parent_name": parent_name,
            "description": org.description,
            "status": org.status,
            "sort_order": org.sort_order,
            "stream_count": stream_count,
            "created_at": org.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return OrganizationListResponse(
        organizations=org_items,
        total=total,
        current=params.current,
        size=params.size
    )


@router.get("/{org_id}", response_model=OrganizationInfo)
def get_organization_detail(
    org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取组织详情
    """
    organization = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    return organization


@router.post("", response_model=OrganizationOperationResponse)
def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    创建新组织
    """
    # 用户有访问权限即可操作
    
    # 验证父组织是否存在
    if org_data.parent_id:
        parent = db.query(Organization).filter(Organization.org_id == org_data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父组织不存在")
    
    # 生成唯一ID
    org_id = generate_unique_id("org")
    
    # 计算路径
    if org_data.parent_id:
        parent = db.query(Organization).filter(Organization.org_id == org_data.parent_id).first()
        path = f"{parent.path}{org_id}/"
    else:
        path = f"/{org_id}/"
    
    # 创建组织
    db_org = Organization(
        org_id=org_id,
        name=org_data.name,
        parent_id=org_data.parent_id,
        path=path,
        description=org_data.description,
        status=org_data.status,
        sort_order=org_data.sort_order
    )
    
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    
    return OrganizationOperationResponse(
        success=True,
        org_id=org_id,
        operation="create",
        message="组织创建成功",
        data={"name": org_data.name, "path": path}
    )


@router.put("/{org_id}", response_model=OrganizationOperationResponse)
def update_organization(
    org_id: str,
    org_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    更新组织信息
    """
    # 用户有访问权限即可操作
    
    organization = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 更新字段
    if org_data.name is not None:
        organization.name = org_data.name
    if org_data.description is not None:
        organization.description = org_data.description
    if org_data.status is not None:
        organization.status = org_data.status
    if org_data.sort_order is not None:
        organization.sort_order = org_data.sort_order
    
    db.commit()
    
    return OrganizationOperationResponse(
        success=True,
        org_id=org_id,
        operation="update",
        message="组织更新成功"
    )


@router.delete("/{org_id}", response_model=OrganizationOperationResponse)
def delete_organization(
    org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    删除组织
    """
    # 用户有访问权限即可操作
    
    organization = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 检查是否有子组织
    children = db.query(Organization).filter(Organization.parent_id == org_id).count()
    if children > 0:
        raise HTTPException(status_code=400, detail=f"无法删除组织，还有 {children} 个子组织")
    
    # 检查是否有绑定的视频流
    bindings = db.query(OrganizationBinding).filter(OrganizationBinding.org_id == org_id).count()
    if bindings > 0:
        raise HTTPException(status_code=400, detail=f"无法删除组织，还有 {bindings} 个绑定的视频流")
    
    db.delete(organization)
    db.commit()
    
    return OrganizationOperationResponse(
        success=True,
        org_id=org_id,
        operation="delete",
        message="组织删除成功"
    )


@router.post("/move", response_model=OrganizationOperationResponse)
def move_organization(
    move_data: OrganizationMoveRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    移动组织到新的父组织下
    """
    # 用户有访问权限即可操作
    
    organization = db.query(Organization).filter(Organization.org_id == move_data.org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证新父组织
    if move_data.new_parent_id:
        new_parent = db.query(Organization).filter(Organization.org_id == move_data.new_parent_id).first()
        if not new_parent:
            raise HTTPException(status_code=400, detail="新父组织不存在")
        
        # 检查是否会形成循环引用
        if move_data.new_parent_id == move_data.org_id:
            raise HTTPException(status_code=400, detail="不能将组织移动到自身下")
        
        # 检查新父组织是否为当前组织的子组织
        if new_parent.path.startswith(organization.path):
            raise HTTPException(status_code=400, detail="不能将组织移动到其子组织下")
    
    # 更新组织路径
    update_organization_path(db, organization, move_data.new_parent_id)
    
    # 如果需要更新子组织路径
    if move_data.update_children_path:
        children = db.query(Organization).filter(Organization.path.like(f"{organization.path}%")).all()
        for child in children:
            if child.org_id != organization.org_id:
                # 重新构建子组织路径
                relative_path = child.path[len(organization.path):]
                child.path = f"{organization.path}{relative_path}"
    
    db.commit()
    
    return OrganizationOperationResponse(
        success=True,
        org_id=move_data.org_id,
        operation="move",
        message="组织移动成功",
        data={"new_parent_id": move_data.new_parent_id, "new_path": organization.path}
    )


@router.get("/{org_id}/streams", response_model=OrganizationStreamsResponse)
def get_organization_streams(
    org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取组织下的所有视频流
    """
    organization = db.query(Organization).filter(Organization.org_id == org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 查询绑定的视频流
    bindings = db.query(OrganizationBinding).filter(OrganizationBinding.org_id == org_id).all()
    stream_ids = [binding.stream_id for binding in bindings]
    
    if not stream_ids:
        return OrganizationStreamsResponse(
            org_id=org_id,
            org_name=organization.name,
            streams=[],
            total=0
        )
    
    streams = db.query(VideoStream).filter(VideoStream.stream_id.in_(stream_ids)).all()
    
    stream_items = []
    for stream in streams:
        stream_items.append({
            "stream_id": stream.stream_id,
            "name": stream.name,
            "url": stream.url,
            "status": stream.status,
            "is_forwarding": stream.is_forwarding if hasattr(stream, 'is_forwarding') else False,
            "created_at": stream.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return OrganizationStreamsResponse(
        org_id=org_id,
        org_name=organization.name,
        streams=stream_items,
        total=len(stream_items)
    ) 