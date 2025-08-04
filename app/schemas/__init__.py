"""
API 模型定义包
包含各种 API 请求和响应的数据模型定义
"""

# 导入各模块的schema定义，便于统一管理和使用
from .auth import *
from .user import *
from .menu import *
from .role import *          # 新增：角色管理相关模型
from .organization import *  # 新增：组织管理相关模型
from .algorithm import *
from .analyzer import *
from .task import *
from .alarm import *
from .stream import *        # 视频流管理相关模型 