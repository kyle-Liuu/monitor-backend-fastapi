from typing import Any, List, Dict
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Menu, User
from app.schemas.menu import MenuItemOut, MenuResponse, AuthItem
from app.utils.utils import get_current_user

router = APIRouter()


def get_menu_tree(db: Session) -> List[MenuItemOut]:
    """
    递归构建菜单树，确保与前端路由配置完全匹配
    """
    # 查询所有菜单
    all_menus = db.query(Menu).order_by(Menu.sort).all()
    
    # 构建菜单树
    menu_dict = {}
    for menu in all_menus:
        # 处理权限列表
        auth_list = None
        if menu.auth_list:
            try:
                auth_items = json.loads(menu.auth_list)
                auth_list = [AuthItem(title=item.get('title', ''), authMark=item.get('authMark', '')) 
                             for item in auth_items]
            except:
                auth_list = None
        
        # 处理角色列表
        roles = menu.roles.split(",") if menu.roles else None
        
        menu_dict[menu.menu_id] = MenuItemOut(
            id=menu.menu_id,
            menu_id=menu.menu_id,
            name=menu.name,
            path=menu.path,
            component=menu.component,
            redirect=menu.redirect,
            meta={
                "title": menu.meta_title,
                "icon": menu.meta_icon,
                "keepAlive": menu.keep_alive,
                "roles": roles,
                "showBadge": menu.show_badge,
                "showTextBadge": menu.show_text_badge,
                "isHide": menu.is_hidden,
                "isHideTab": menu.is_hide_tab,
                "isFullPage": menu.is_full_page,
                "fixedTab": menu.fixed_tab,
                "activePath": menu.active_path,
                "link": menu.link,
                "isIframe": menu.is_iframe,
                "isFirstLevel": menu.is_first_level,
                "authList": auth_list
            },
            children=[]
        )
    
    # 构建树状结构
    root_menus = []
    for menu in all_menus:
        if menu.parent_id is None:
            root_menus.append(menu_dict[menu.menu_id])
        else:
            parent = menu_dict.get(menu.parent_id)
            if parent:
                parent.children.append(menu_dict[menu.menu_id])
    
    return root_menus


def get_menu_tree_by_role(db: Session, user_roles: List[str]) -> List[MenuItemOut]:
    """
    递归构建菜单树，根据用户角色过滤，确保与前端路由配置完全匹配
    """
    # 查询所有菜单
    all_menus = db.query(Menu).order_by(Menu.sort).all()
    
    # 过滤有权限访问的菜单
    filtered_menus = []
    for menu in all_menus:
        # 检查菜单是否有角色限制
        if menu.roles:
            allowed_roles = menu.roles.split(",")
            # 检查用户是否拥有任一允许的角色
            if not any(role in allowed_roles for role in user_roles):
                continue  # 用户角色不在允许的角色列表中，跳过此菜单
        
        filtered_menus.append(menu)
    
    # 构建菜单树
    menu_dict = {}
    for menu in filtered_menus:
        # 处理权限列表
        auth_list = None
        if menu.auth_list:
            try:
                auth_items = json.loads(menu.auth_list)
                auth_list = [AuthItem(title=item.get('title', ''), authMark=item.get('authMark', '')) 
                             for item in auth_items]
            except:
                auth_list = None
        
        # 处理角色列表
        roles = menu.roles.split(",") if menu.roles else None
        
        menu_dict[menu.menu_id] = MenuItemOut(
            id=menu.menu_id,
            menu_id=menu.menu_id,
            name=menu.name,
            path=menu.path,
            component=menu.component,
            redirect=menu.redirect,
            meta={
                "title": menu.meta_title,
                "icon": menu.meta_icon,
                "keepAlive": menu.keep_alive,
                "roles": roles,
                "showBadge": menu.show_badge,
                "showTextBadge": menu.show_text_badge,
                "isHide": menu.is_hidden,
                "isHideTab": menu.is_hide_tab,
                "isFullPage": menu.is_full_page,
                "fixedTab": menu.fixed_tab,
                "activePath": menu.active_path,
                "link": menu.link,
                "isIframe": menu.is_iframe,
                "isFirstLevel": menu.is_first_level,
                "authList": auth_list
            },
            children=[]
        )
    
    # 构建树状结构
    root_menus = []
    for menu in filtered_menus:
        if menu.parent_id is None:
            # 检查菜单是否在过滤后的字典中
            if menu.menu_id in menu_dict:
                root_menus.append(menu_dict[menu.menu_id])
        else:
            parent = menu_dict.get(menu.parent_id)
            if parent and menu.menu_id in menu_dict:
                parent.children.append(menu_dict[menu.menu_id])
    
    return root_menus


@router.get("/list", response_model=MenuResponse)
def get_menu_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取菜单列表，根据用户角色返回不同的菜单
    """
    try:
        # 解析用户角色列表
        user_roles = current_user.role.split(",") if current_user.role else []
        
        if "R_SUPER" in user_roles:
            # 超级管理员可以看到所有菜单
            menus = get_menu_tree(db)
        else:
            # 根据角色过滤菜单
            menus = get_menu_tree_by_role(db, user_roles)
        
        return {
            "code": 200,
            "data": {"menuList": menus},
            "msg": "获取菜单成功"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取菜单失败: {str(e)}")


@router.get("/all", response_model=MenuResponse)
def get_all_menus(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取所有菜单（只有超级管理员可以访问）
    """
    try:
        if not current_user.has_role("R_SUPER"):
            raise HTTPException(status_code=403, detail="没有权限访问")
        
        menus = get_menu_tree(db)
        
        return {
            "code": 200,
            "data": {"menuList": menus},
            "msg": "获取所有菜单成功"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取菜单失败: {str(e)}")


@router.get("/{menu_id}", response_model=Dict)
def get_menu_by_id(
    menu_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    根据ID获取菜单详情
    """
    try:
        if not current_user.has_role("R_SUPER"):
            raise HTTPException(status_code=403, detail="没有权限访问")
        
        menu = db.query(Menu).filter(Menu.menu_id == menu_id).first()
        
        if not menu:
            raise HTTPException(status_code=404, detail="菜单不存在")
        
        return {
            "code": 200,
            "data": {
                "id": menu.menu_id,
                "name": menu.name,
                "path": menu.path,
                "component": menu.component,
                "redirect": menu.redirect or "",
                "parentId": menu.parent_id or "",
                "metaTitle": menu.meta_title,
                "metaIcon": menu.meta_icon,
                "sort": menu.sort,
                "isHidden": menu.is_hidden,
                "roles": menu.roles or "",
                "keepAlive": menu.keep_alive,
                "authList": menu.auth_list or "[]",
                "showBadge": menu.show_badge,
                "showTextBadge": menu.show_text_badge,
                "isHideTab": menu.is_hide_tab,
                "isFullPage": menu.is_full_page,
                "fixedTab": menu.fixed_tab,
                "activePath": menu.active_path or "",
                "link": menu.link or "",
                "isIframe": menu.is_iframe,
                "isFirstLevel": menu.is_first_level
            },
            "msg": "获取菜单详情成功"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取菜单详情失败: {str(e)}")
