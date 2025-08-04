"""
数据访问层初始化文件
"""

from .base import BaseDAO
from .stream_dao import StreamDAO

# 初始化连接池
import os
from .base import BaseDAO

# 获取数据库路径
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))), "app.db")

# 初始化连接池
BaseDAO.init_pool(db_path, max_connections=5)

# 导出DAO类
__all__ = ['StreamDAO'] 