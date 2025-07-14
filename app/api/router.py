from fastapi import APIRouter

from app.api.endpoints import auth, menu, users

# API路由
api_router = APIRouter()

# 添加各模块路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(menu.router, prefix="/menu", tags=["menu"])
api_router.include_router(users.router, prefix="/user", tags=["user"]) 