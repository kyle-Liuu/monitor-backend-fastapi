"""
数据访问层基类
- 提供SQLite连接池
- 统一数据库操作接口
- 简化事务处理
"""

import sqlite3
import threading
import queue
from typing import Dict, List, Any, Optional, Tuple, Callable
import logging

logger = logging.getLogger(__name__)

class ConnectionPool:
    """SQLite连接池"""
    
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = queue.Queue(maxsize=max_connections)
        self.lock = threading.RLock()
        self._fill_pool()
    
    def _fill_pool(self):
        """初始化连接池"""
        for _ in range(self.max_connections):
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
            self.connections.put(conn)
    
    def get_connection(self):
        """获取连接"""
        return self.connections.get(block=True, timeout=5.0)
    
    def release_connection(self, conn):
        """释放连接回池"""
        if self.connections.full():
            conn.close()
        else:
            self.connections.put(conn)
    
    def close_all(self):
        """关闭所有连接"""
        while not self.connections.empty():
            conn = self.connections.get()
            conn.close()


class BaseDAO:
    """基础数据访问对象"""
    
    _pool = None
    _lock = threading.RLock()
    
    @classmethod
    def init_pool(cls, db_path: str, max_connections: int = 5):
        """初始化连接池"""
        with cls._lock:
            # 如果已有连接池，先关闭
            if cls._pool is not None:
                cls._pool.close_all()
            cls._pool = ConnectionPool(db_path, max_connections)
    
    @classmethod
    def get_pool(cls) -> ConnectionPool:
        """获取连接池"""
        return cls._pool
    
    @classmethod
    def close_pool(cls):
        """关闭连接池"""
        with cls._lock:
            if cls._pool is not None:
                cls._pool.close_all()
                cls._pool = None
    
    def __init__(self):
        """初始化DAO"""
        if self._pool is None:
            raise RuntimeError("必须先调用init_pool初始化连接池")
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """执行查询"""
        conn = self._pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            results = [dict(row) for row in cursor.fetchall()]
            return results
        finally:
            self._pool.release_connection(conn)
    
    def execute_update(self, query: str, params: tuple = None) -> int:
        """执行更新并返回影响的行数"""
        conn = self._pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.rowcount
        finally:
            self._pool.release_connection(conn)
    
    def execute_insert(self, query: str, params: tuple = None) -> int:
        """执行插入并返回新行ID"""
        conn = self._pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            conn.commit()
            return cursor.lastrowid
        finally:
            self._pool.release_connection(conn)
    
    def transaction(self, func: Callable):
        """事务处理装饰器"""
        def wrapper(*args, **kwargs):
            conn = self._pool.get_connection()
            try:
                result = func(conn, *args, **kwargs)
                conn.commit()
                return result
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                self._pool.release_connection(conn)
        return wrapper 