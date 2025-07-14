from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class AuthItem(BaseModel):
    """
    菜单权限项
    """
    title: str
    authMark: str


class MetaInfo(BaseModel):
    """
    菜单元数据 - 与前端路由配置完全匹配
    """
    title: str
    icon: Optional[str] = None
    keepAlive: Optional[bool] = True
    roles: Optional[List[str]] = None
    showTextBadge: Optional[str] = None
    showBadge: Optional[bool] = None
    fixedTab: Optional[bool] = None
    isHide: Optional[bool] = None
    isHideTab: Optional[bool] = None
    isFullPage: Optional[bool] = None
    activePath: Optional[str] = None
    link: Optional[str] = None
    isIframe: Optional[bool] = None
    authList: Optional[List[AuthItem]] = None
    isFirstLevel: Optional[bool] = None


class MenuBase(BaseModel):
    """
    菜单基础模型
    """
    name: str
    path: str
    component: Optional[str] = None
    redirect: Optional[str] = None
    meta: MetaInfo


class MenuCreate(MenuBase):
    """
    创建菜单时的模型
    """
    parent_id: Optional[str] = None
    sort: int = 0


class MenuItemOut(MenuBase):
    """
    返回给前端的菜单项 - 与前端路由配置完全匹配
    """
    menu_id: str = Field(..., alias="id")
    children: Optional[List["MenuItemOut"]] = []

    class Config:
        from_attributes = True
        populate_by_name = True


# 递归引用
MenuItemOut.update_forward_refs()


class MenuResponse(BaseModel):
    """
    菜单响应，符合前端接口要求
    """
    code: int = 200
    msg: str = "操作成功"
    data: Dict[str, List[MenuItemOut]] = Field(..., alias="data")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "code": 200,
                "msg": "操作成功",
                "data": {
                    "menuList": []
                }
            }
        } 