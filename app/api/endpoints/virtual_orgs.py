"""
虚拟组织管理API端点
提供虚拟组织和组织绑定的完整管理功能
"""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.db.database import get_db
from app.db.models import Organization, OrganizationBinding, VideoStream
from app.schemas.organization import (
    OrganizationBindingCreate, OrganizationBindingInfo, OrganizationBindingListResponse,
    OrganizationBindingBatchRequest, OrganizationBindingBatchResponse,
    VirtualOrganizationCreate, VirtualOrganizationInfo, VirtualOrganizationListResponse
)
from app.utils.utils import get_current_user, generate_unique_id

router = APIRouter()


# ============================================================================
# 组织绑定管理
# ============================================================================

@router.post("/bindings", response_model=dict)
def create_organization_binding(
    binding_data: OrganizationBindingCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    创建组织和视频流的绑定关系
    """
    # 用户有访问权限即可操作
    
    # 验证组织是否存在
    organization = db.query(Organization).filter(Organization.org_id == binding_data.org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    # 验证视频流是否存在
    stream = db.query(VideoStream).filter(VideoStream.stream_id == binding_data.stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="视频流不存在")
    
    # 检查绑定关系是否已存在
    existing = db.query(OrganizationBinding).filter(
        OrganizationBinding.org_id == binding_data.org_id,
        OrganizationBinding.stream_id == binding_data.stream_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="绑定关系已存在")
    
    # 创建绑定
    binding_id = generate_unique_id("bind")
    db_binding = OrganizationBinding(
        binding_id=binding_id,
        org_id=binding_data.org_id,
        stream_id=binding_data.stream_id
    )
    
    db.add(db_binding)
    db.commit()
    db.refresh(db_binding)
    
    return {
        "success": True,
        "binding_id": binding_id,
        "org_id": binding_data.org_id,
        "stream_id": binding_data.stream_id,
        "message": "绑定创建成功"
    }


@router.get("/bindings", response_model=OrganizationBindingListResponse)
def get_organization_bindings(
    org_id: str = Query(None, description="组织ID过滤"),
    stream_id: str = Query(None, description="视频流ID过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取组织绑定列表
    """
    query = db.query(OrganizationBinding)
    
    # 过滤条件
    if org_id:
        query = query.filter(OrganizationBinding.org_id == org_id)
    if stream_id:
        query = query.filter(OrganizationBinding.stream_id == stream_id)
    
    bindings = query.all()
    
    # 构造响应数据
    binding_items = []
    for binding in bindings:
        # 获取组织名称
        org = db.query(Organization).filter(Organization.org_id == binding.org_id).first()
        org_name = org.name if org else None
        
        # 获取视频流名称
        stream = db.query(VideoStream).filter(VideoStream.stream_id == binding.stream_id).first()
        stream_name = stream.name if stream else None
        
        binding_items.append(OrganizationBindingInfo(
            binding_id=binding.binding_id,
            org_id=binding.org_id,
            stream_id=binding.stream_id,
            org_name=org_name,
            stream_name=stream_name,
            created_at=binding.created_at
        ))
    
    return OrganizationBindingListResponse(
        bindings=binding_items,
        total=len(binding_items)
    )


@router.delete("/bindings/{binding_id}", response_model=dict)
def delete_organization_binding(
    binding_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    删除组织绑定关系
    """
    # 用户有访问权限即可操作
    
    binding = db.query(OrganizationBinding).filter(OrganizationBinding.binding_id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="绑定关系不存在")
    
    db.delete(binding)
    db.commit()
    
    return {
        "success": True,
        "binding_id": binding_id,
        "message": "绑定删除成功"
    }


@router.post("/bindings/batch", response_model=OrganizationBindingBatchResponse)
def batch_create_bindings(
    batch_data: OrganizationBindingBatchRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    批量创建组织绑定
    """
    # 用户有访问权限即可操作
    
    # 验证组织是否存在
    organization = db.query(Organization).filter(Organization.org_id == batch_data.org_id).first()
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")
    
    processed_count = 0
    failed_count = 0
    details = []
    
    for stream_id in batch_data.stream_ids:
        try:
            # 验证视频流是否存在
            stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
            if not stream:
                failed_count += 1
                details.append({"stream_id": stream_id, "error": "视频流不存在"})
                continue
            
            # 检查绑定是否已存在
            existing = db.query(OrganizationBinding).filter(
                OrganizationBinding.org_id == batch_data.org_id,
                OrganizationBinding.stream_id == stream_id
            ).first()
            if existing:
                failed_count += 1
                details.append({"stream_id": stream_id, "error": "绑定关系已存在"})
                continue
            
            # 创建绑定
            binding_id = generate_unique_id("bind")
            db_binding = OrganizationBinding(
                binding_id=binding_id,
                org_id=batch_data.org_id,
                stream_id=stream_id
            )
            db.add(db_binding)
            processed_count += 1
            
        except Exception as e:
            failed_count += 1
            details.append({"stream_id": stream_id, "error": str(e)})
    
    db.commit()
    
    return OrganizationBindingBatchResponse(
        success=failed_count == 0,
        org_id=batch_data.org_id,
        processed_count=processed_count,
        failed_count=failed_count,
        message=f"批量绑定完成，成功{processed_count}个，失败{failed_count}个",
        details=details if failed_count > 0 else None
    )


# ============================================================================
# 虚拟组织管理（简化版，主要用于分组展示）
# ============================================================================

@router.get("", response_model=VirtualOrganizationListResponse)
def get_virtual_organizations(
    skip: int = Query(0, ge=0, description="跳过数量"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    name: str = Query(None, description="名称搜索"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取虚拟组织列表
    """
    # 虚拟组织功能简化实现，主要用于分组展示
    # 实际项目中可能需要真实的VirtualOrganization表
    
    # 这里返回一个模拟的响应，实际使用时可以根据需要实现
    virtual_orgs = []
    
    # 示例：基于现有组织创建虚拟分组
    organizations = db.query(Organization).limit(5).all()
    for i, org in enumerate(organizations):
        # 统计该组织下的视频流数量
        stream_count = db.query(OrganizationBinding).filter(
            OrganizationBinding.org_id == org.org_id
        ).count()
        
        virtual_orgs.append(VirtualOrganizationInfo(
            virtual_org_id=f"vorg_{org.org_id}",
            name=f"虚拟分组-{org.name}",
            description=f"基于{org.name}的虚拟分组",
            org_count=1,
            stream_count=stream_count,
            created_at=org.created_at,
            updated_at=org.updated_at
        ))
    
    return VirtualOrganizationListResponse(
        virtual_orgs=virtual_orgs,
        total=len(virtual_orgs)
    )


@router.post("", response_model=dict)
def create_virtual_organization(
    virtual_org_data: VirtualOrganizationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    创建虚拟组织
    """
    # 用户有访问权限即可操作
    
    # 简化实现：虚拟组织主要用于前端分组展示
    # 这里可以根据实际需求实现真正的虚拟组织逻辑
    
    virtual_org_id = generate_unique_id("vorg")
    
    return {
        "success": True,
        "virtual_org_id": virtual_org_id,
        "name": virtual_org_data.name,
        "message": "虚拟组织创建成功（简化实现）"
    }


@router.get("/{virtual_org_id}", response_model=dict)
def get_virtual_organization_detail(
    virtual_org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取虚拟组织详情
    """
    # 简化实现
    return {
        "virtual_org_id": virtual_org_id,
        "name": "示例虚拟组织",
        "description": "这是一个示例虚拟组织",
        "org_refs": [],
        "devices": []
    }


@router.delete("/{virtual_org_id}", response_model=dict)
def delete_virtual_organization(
    virtual_org_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    删除虚拟组织
    """
    # 用户有访问权限即可操作
    
    # 简化实现
    return {
        "success": True,
        "virtual_org_id": virtual_org_id,
        "message": "虚拟组织删除成功（简化实现）"
    }


# ============================================================================
# 辅助接口
# ============================================================================

@router.get("/bindings/stream/{stream_id}/organization", response_model=dict)
def get_stream_organization(
    stream_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    获取视频流绑定的组织信息
    """
    binding = db.query(OrganizationBinding).filter(OrganizationBinding.stream_id == stream_id).first()
    
    if not binding:
        return {
            "stream_id": stream_id,
            "organization": None,
            "message": "该视频流未绑定组织"
        }
    
    organization = db.query(Organization).filter(Organization.org_id == binding.org_id).first()
    
    return {
        "stream_id": stream_id,
        "organization": {
            "org_id": organization.org_id,
            "name": organization.name,
            "path": organization.path
        } if organization else None,
        "binding_id": binding.binding_id,
        "created_at": binding.created_at.strftime("%Y-%m-%d %H:%M:%S")
    }


@router.delete("/bindings/stream/{stream_id}", response_model=dict)
def unbind_stream_from_organization(
    stream_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    """
    解除视频流的组织绑定
    """
    # 用户有访问权限即可操作
    
    binding = db.query(OrganizationBinding).filter(OrganizationBinding.stream_id == stream_id).first()
    
    if not binding:
        return {
            "success": True,
            "stream_id": stream_id,
            "message": "该视频流未绑定组织，无需解除"
        }
    
    db.delete(binding)
    db.commit()
    
    return {
        "success": True,
        "stream_id": stream_id,
        "binding_id": binding.binding_id,
        "message": "解除绑定成功"
    } 