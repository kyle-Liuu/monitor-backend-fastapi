from fastapi import APIRouter, Depends

from app.api.endpoints import auth, menu, users
# 添加角色管理API
from app.api.endpoints import roles
# 添加组织管理API
from app.api.endpoints import organizations
# 添加虚拟组织管理API
from app.api.endpoints import virtual_orgs
# 添加视频流管理API（独立模块）
from app.api.endpoints import streams
# 添加算法管理API（独立模块）
from app.api.endpoints import algorithms
# 添加分析器API（专注AI分析业务）
from app.api.endpoints import analyzer
# 添加WebSocket接口（独立模块）
from app.api.endpoints import websocket_alarms
from app.api.endpoints import websocket_status
from app.utils.utils import get_current_active_user

# API路由
api_router = APIRouter()

# ============================================================================
# 基础平台路由（认证、菜单、用户管理）
# ============================================================================
api_router.include_router(auth.router, prefix="", tags=["认证"])
api_router.include_router(menu.router, prefix="/menu", tags=["菜单"])
api_router.include_router(users.router, prefix="/user", tags=["用户"])

# 角色管理（查看权限开放，操作权限仅超级管理员）
api_router.include_router(
    roles.router,
    prefix="/roles",
    tags=["角色管理"],
    dependencies=[Depends(get_current_active_user)]
)

# 组织管理（有页面访问权限即可操作）
api_router.include_router(
    organizations.router,
    prefix="/organizations",
    tags=["组织管理"],
    dependencies=[Depends(get_current_active_user)]
)

# 虚拟组织管理（有页面访问权限即可操作）
api_router.include_router(
    virtual_orgs.router,
    prefix="/virtual-orgs",
    tags=["虚拟组织管理"],
    dependencies=[Depends(get_current_active_user)]
)

# ============================================================================
# 核心业务模块路由
# ============================================================================

# 视频流管理（独立功能，专注流的完整生命周期管理）
api_router.include_router(
    streams.router,
    prefix="/streams",
    tags=["视频流管理"],
    dependencies=[Depends(get_current_active_user)]
)

# 算法包管理（独立功能，完整的算法生命周期管理）
api_router.include_router(
    algorithms.router,
    prefix="/algorithms",
    tags=["算法包管理"],
    dependencies=[Depends(get_current_active_user)]
)

# AI分析器（专注AI分析业务：任务管理、告警管理、系统控制、输出管理）
api_router.include_router(
    analyzer.router,
    prefix="/analyzer",
    tags=["AI分析器"],
    dependencies=[Depends(get_current_active_user)]
)
# ============================================================================
# WebSocket实时通信路由
# ============================================================================

# WebSocket告警推送（无需认证依赖，连接后处理）
api_router.include_router(
    websocket_alarms.router,
    prefix="/ws",
    tags=["WebSocket告警推送"]
)

# WebSocket状态推送（无需认证依赖，连接后处理）
api_router.include_router(
    websocket_status.router,
    prefix="/ws", 
    tags=["WebSocket状态推送"]
)