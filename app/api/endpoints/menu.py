from typing import Any, List, Dict
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Menu, User
from app.schemas.menu import MenuItemOut, MenuResponse, AuthItem
from app.utils.utils import get_current_user

router = APIRouter()


async def get_menu_tree(db: AsyncSession) -> List[MenuItemOut]:
    """
    递归构建菜单树，确保与前端路由配置完全匹配
    """
    # 查询所有菜单
    result = await db.execute(select(Menu).order_by(Menu.sort))
    all_menus = result.scalars().all()
    
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


async def get_menu_tree_by_role(db: AsyncSession, user_role: str) -> List[MenuItemOut]:
    """
    递归构建菜单树，根据用户角色过滤，确保与前端路由配置完全匹配
    """
    # 查询所有菜单
    result = await db.execute(select(Menu).order_by(Menu.sort))
    all_menus = result.scalars().all()
    
    # 过滤有权限访问的菜单
    filtered_menus = []
    for menu in all_menus:
        # 检查菜单是否有角色限制
        if menu.roles:
            allowed_roles = menu.roles.split(",")
            if user_role not in allowed_roles:
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
        
        # 不再向前端返回roles字段，因为已经过滤过了
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
    
    # 构建树状结构 - 只包含用户有权限的菜单
    root_menus = []
    for menu in filtered_menus:
        if menu.parent_id is None:
            root_menus.append(menu_dict[menu.menu_id])
        else:
            # 只有当父菜单存在于过滤后的菜单列表中才添加子菜单
            if menu.parent_id in menu_dict:
                parent = menu_dict.get(menu.parent_id)
                if parent:
                    parent.children.append(menu_dict[menu.menu_id])
    
    return root_menus


@router.get("/list", response_model=MenuResponse)
async def get_menu_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取菜单列表，根据当前用户角色过滤，只返回有权限访问的菜单
    """
    try:
        # 使用用户角色获取过滤后的菜单树
        menu_list = await get_menu_tree_by_role(db, current_user.role)
        return {
            "code": 200,
            "message": "获取菜单成功",
            "data": {
                "menuList": menu_list
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取菜单失败: {str(e)}")
