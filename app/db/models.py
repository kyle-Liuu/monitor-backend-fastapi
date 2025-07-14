from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.db.database import Base


class User(Base):
    """
    用户模型
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(20), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    fullname = Column(String(100))
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    is_admin = Column(Boolean(), default=False)
    avatar = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, default="R_USER")  # R_SUPER, R_ADMIN, R_USER
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Menu(Base):
    """
    菜单模型 - 与前端路由配置完全匹配
    """
    __tablename__ = "menus"

    # 数据库主键，自增ID
    id = Column(Integer, primary_key=True, index=True)
    
    # 菜单唯一标识，格式为"menu"+随机字符，如"menuA1B2C3D"
    menu_id = Column(String(20), unique=True, index=True, nullable=False)
    
    # 菜单名称，对应前端路由的name，如"Dashboard"、"User"
    name = Column(String(50), nullable=False)
    
    # 菜单路径，对应前端路由的path，如"/dashboard"、"/system/user"
    path = Column(String(100), nullable=False)
    
    # 组件路径，对应前端路由的component，如"/index/index"、"/system/user"
    component = Column(String(100), nullable=True)
    
    # 重定向路径，路由重定向时使用，如"/dashboard/console"
    redirect = Column(String(100), nullable=True)
    
    # 菜单标题，通常是i18n的key，如"menus.dashboard.title"
    meta_title = Column(String(100), nullable=False)
    
    # 菜单图标，使用HTML实体编码，如"&#xe721;"
    meta_icon = Column(String(50), nullable=True)
    
    # 父菜单ID，关联到menus表的menu_id，如父菜单ID为"menuA1B2C3D"
    parent_id = Column(String(20), ForeignKey("menus.menu_id"), nullable=True)
    
    # 菜单排序，数字越小排越前面，如1、2、3
    sort = Column(Integer, default=0)
    
    # 是否在菜单中隐藏，如true表示隐藏，false表示显示
    is_hidden = Column(Boolean, default=False)
    
    # 角色权限，用逗号分隔的角色列表，如"R_SUPER,R_ADMIN"
    roles = Column(String(200), nullable=True)
    
    # 是否缓存页面，如true表示缓存，false表示不缓存
    keep_alive = Column(Boolean, default=True)
    
    # 操作权限列表，JSON格式，如[{"title":"新增","authMark":"add"},{"title":"编辑","authMark":"edit"}]
    auth_list = Column(Text, nullable=True)
    
    # 是否显示徽章，如true表示显示，false表示不显示
    show_badge = Column(Boolean, default=False)
    
    # 文本徽章内容，如"New"、"Hot"
    show_text_badge = Column(String(50), nullable=True)
    
    # 是否在标签页中隐藏，如true表示隐藏，false表示显示
    is_hide_tab = Column(Boolean, default=False)
    
    # 是否为全屏页面，如true表示全屏，false表示不全屏
    is_full_page = Column(Boolean, default=False)
    
    # 是否固定标签页，如true表示固定，false表示不固定
    fixed_tab = Column(Boolean, default=False)
    
    # 激活菜单路径，用于标识当前激活的菜单，如"/dashboard/console"
    active_path = Column(String(100), nullable=True)
    
    # 外部链接，如"https://element-plus.org/zh-CN/component/overview.html"
    link = Column(String(200), nullable=True)
    
    # 是否为iframe，如true表示是iframe，false表示不是
    is_iframe = Column(Boolean, default=False)
    
    # 是否为一级菜单，如true表示是一级菜单，false表示不是
    is_first_level = Column(Boolean, default=False)
    
    # 创建时间
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 更新时间，自动在更新时设置
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 自引用关系，修复级联删除问题
    children = relationship("Menu", 
                           backref="parent",
                           remote_side=[menu_id],
                           cascade="all, delete") 


class BlacklistedToken(Base):
    """
    已失效令牌黑名单
    """
    __tablename__ = "blacklisted_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow) 