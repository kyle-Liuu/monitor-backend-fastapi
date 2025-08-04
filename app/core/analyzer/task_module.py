"""
任务管理模块 - 管理视频分析任务
- 支持视频流和算法的多对多关系
- 一个视频流+一个算法=一个任务
- 支持任务状态监控和资源管理
"""

import sqlite3
import threading
import time
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# 导入事件总线
from .event_bus import get_event_bus, Event
from .utils.id_generator import generate_unique_id

logger = logging.getLogger(__name__)

class TaskModule:
    """任务管理模块，负责视频分析任务的生命周期管理"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = TaskModule()
            return cls._instance
    
    def __init__(self):
        """初始化任务管理器"""
        # 基本属性
        self.running = False
        self.lock = threading.RLock()
        
        # 数据库路径
        import os
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "app.db")
        
        # 任务缓存
        self.tasks = {}  # {task_id: task_info}
        self.task_status = {}  # {task_id: status}
        self.task_configs = {}  # {task_id: config}
        
        # 事件总线
        self.event_bus = get_event_bus()
        
        # 初始化数据库表
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    stream_id TEXT NOT NULL,
                    algorithm_id TEXT NOT NULL,
                    status TEXT DEFAULT 'created',
                    config TEXT,
                    alarm_config TEXT,
                    frame_count INTEGER DEFAULT 0,
                    last_frame_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (stream_id) REFERENCES streams (stream_id),
                    FOREIGN KEY (algorithm_id) REFERENCES algorithms (algo_id)
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("任务数据库表初始化完成")
            
        except Exception as e:
            logger.error(f"初始化任务数据库表异常: {e}")
    
    def start(self):
        """启动任务模块"""
        if self.running:
            return True
        
        logger.info("启动任务管理模块")
        self.running = True
        
        # 发布模块启动事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "task_module",
            {"module": "task", "status": True}
        ))
        
        # 恢复之前的任务
        self._recover_tasks()
        
        return True
    
    def stop(self):
        """停止任务模块"""
        if not self.running:
            return True
        
        logger.info("停止任务管理模块")
        
        # 停止所有任务
        self._stop_all_tasks()
        
        self.running = False
        
        # 发布模块停止事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "task_module",
            {"module": "task", "status": False}
        ))
        
        return True
    
    def _recover_tasks(self):
        """恢复之前的任务"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT task_id, status FROM tasks WHERE status IN ('running', 'active')")
            active_tasks = cursor.fetchall()
            
            conn.close()
            
            for task_id, status in active_tasks:
                # 将状态重置为created，等待重新启动
                self._update_task_status(task_id, "created")
                logger.info(f"恢复任务: {task_id}, 状态: {status}")
                
        except Exception as e:
            logger.error(f"恢复任务异常: {e}")
    
    def _stop_all_tasks(self):
        """停止所有任务"""
        with self.lock:
            for task_id in list(self.task_status.keys()):
                self._update_task_status(task_id, "stopped")
    
    def create_task(self, stream_id: str, algorithm_id: str, name: str = None, 
                   description: str = "", config: Dict = None, alarm_config: Dict = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """创建任务"""
        if not self.running:
            return False, "模块未运行", None
            
        with self.lock:
            try:
                # 生成任务ID
                task_id = generate_unique_id("task")
                
                # 检查流和算法是否存在
                if not self._check_stream_exists(stream_id):
                    return False, f"流不存在: {stream_id}", None
                
                if not self._check_algorithm_exists(algorithm_id):
                    return False, f"算法不存在: {algorithm_id}", None
                
                # 检查是否已存在相同的任务
                if self._check_task_exists(stream_id, algorithm_id):
                    return False, f"任务已存在: {stream_id} + {algorithm_id}", None
                
                # 创建任务记录
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT INTO tasks (task_id, name, description, stream_id, algorithm_id, status, config, alarm_config)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        name or f"Task_{task_id}",
                        description,
                        stream_id,
                        algorithm_id,
                        "created",
                        json.dumps(config or {}),
                        json.dumps(alarm_config or {})
                    )
                )
                conn.commit()
                conn.close()
                
                # 缓存任务信息
                self.tasks[task_id] = {
                    "task_id": task_id,
                    "name": name or f"Task_{task_id}",
                    "description": description,
                    "stream_id": stream_id,
                    "algorithm_id": algorithm_id,
                    "status": "created",
                    "config": config or {},
                    "alarm_config": alarm_config or {},
                    "created_at": datetime.now().isoformat()
                }
                
                self.task_status[task_id] = "created"
                self.task_configs[task_id] = config or {}
                
                # 发布任务创建事件
                self.event_bus.publish(Event(
                    "task.created",
                    "task_module",
                    {"task_id": task_id, "stream_id": stream_id, "algorithm_id": algorithm_id}
                ))
                
                logger.info(f"创建任务: {task_id}, 流: {stream_id}, 算法: {algorithm_id}")
                return True, None, task_id
                
            except Exception as e:
                logger.error(f"创建任务异常: {e}")
                return False, str(e), None
    
    def start_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """启动任务"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                # 检查任务是否存在
                if task_id not in self.tasks:
                    return False, f"任务不存在: {task_id}"
                
                # 检查任务状态
                current_status = self.task_status.get(task_id, "unknown")
                if current_status == "running":
                    return True, "任务已在运行"
                
                # 更新任务状态
                self._update_task_status(task_id, "running")
                
                # 发布任务启动事件
                self.event_bus.publish(Event(
                    "task.started",
                    "task_module",
                    {"task_id": task_id}
                ))
                
                logger.info(f"启动任务: {task_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"启动任务异常: {e}")
                return False, str(e)
    
    def stop_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """停止任务"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                # 检查任务是否存在
                if task_id not in self.tasks:
                    return False, f"任务不存在: {task_id}"
                
                # 更新任务状态
                self._update_task_status(task_id, "stopped")
                
                # 发布任务停止事件
                self.event_bus.publish(Event(
                    "task.stopped",
                    "task_module",
                    {"task_id": task_id}
                ))
                
                logger.info(f"停止任务: {task_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"停止任务异常: {e}")
                return False, str(e)
    
    def delete_task(self, task_id: str) -> Tuple[bool, Optional[str]]:
        """删除任务"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                # 先停止任务
                self.stop_task(task_id)
                
                # 删除数据库记录
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                conn.close()
                
                # 清理缓存
                if task_id in self.tasks:
                    del self.tasks[task_id]
                if task_id in self.task_status:
                    del self.task_status[task_id]
                if task_id in self.task_configs:
                    del self.task_configs[task_id]
                
                # 发布任务删除事件
                self.event_bus.publish(Event(
                    "task.deleted",
                    "task_module",
                    {"task_id": task_id}
                ))
                
                logger.info(f"删除任务: {task_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"删除任务异常: {e}")
                return False, str(e)
    
    def get_task_info(self, task_id: str = None) -> Dict[str, Any]:
        """获取任务信息"""
        if not self.running:
            return {}
            
        with self.lock:
            try:
                if task_id:
                    # 获取单个任务信息
                    if task_id in self.tasks:
                        return self.tasks[task_id].copy()
                    else:
                        return {}
                else:
                    # 获取所有任务信息
                    return {
                        "total": len(self.tasks),
                        "tasks": list(self.tasks.values())
                    }
                    
            except Exception as e:
                logger.error(f"获取任务信息异常: {e}")
                return {}
    
    def get_tasks_by_stream(self, stream_id: str) -> List[Dict[str, Any]]:
        """根据流ID获取任务列表"""
        if not self.running:
            return []
            
        with self.lock:
            try:
                tasks = []
                for task_info in self.tasks.values():
                    if task_info["stream_id"] == stream_id:
                        tasks.append(task_info.copy())
                return tasks
                    
            except Exception as e:
                logger.error(f"根据流ID获取任务异常: {e}")
                return []
    
    def get_tasks_by_algorithm(self, algorithm_id: str) -> List[Dict[str, Any]]:
        """根据算法ID获取任务列表"""
        if not self.running:
            return []
            
        with self.lock:
            try:
                tasks = []
                for task_info in self.tasks.values():
                    if task_info["algorithm_id"] == algorithm_id:
                        tasks.append(task_info.copy())
                return tasks
                    
            except Exception as e:
                logger.error(f"根据算法ID获取任务异常: {e}")
                return []
    
    def update_task_progress(self, task_id: str, frame_count: int = None, 
                           last_frame_time: float = None) -> Tuple[bool, Optional[str]]:
        """更新任务进度"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                if task_id not in self.tasks:
                    return False, f"任务不存在: {task_id}"
                
                # 更新数据库
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                update_fields = []
                params = []
                
                if frame_count is not None:
                    update_fields.append("frame_count = ?")
                    params.append(frame_count)
                
                if last_frame_time is not None:
                    update_fields.append("last_frame_time = ?")
                    params.append(last_frame_time)
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(task_id)
                    
                    cursor.execute(
                        f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = ?",
                        params
                    )
                    conn.commit()
                
                conn.close()
                
                # 更新缓存
                if frame_count is not None:
                    self.tasks[task_id]["frame_count"] = frame_count
                if last_frame_time is not None:
                    self.tasks[task_id]["last_frame_time"] = last_frame_time
                
                logger.debug(f"更新任务进度: {task_id}, 帧数: {frame_count}, 时间: {last_frame_time}")
                return True, None
                
            except Exception as e:
                logger.error(f"更新任务进度异常: {e}")
                return False, str(e)
    
    def _check_stream_exists(self, stream_id: str) -> bool:
        """检查流是否存在"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT stream_id FROM streams WHERE stream_id = ?", (stream_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"检查流存在异常: {e}")
            return False
    
    def _check_algorithm_exists(self, algorithm_id: str) -> bool:
        """检查算法是否存在"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT algo_id FROM algorithms WHERE algo_id = ?", (algorithm_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"检查算法存在异常: {e}")
            return False
    
    def _check_task_exists(self, stream_id: str, algorithm_id: str) -> bool:
        """检查任务是否已存在"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT task_id FROM tasks WHERE stream_id = ? AND algorithm_id = ?",
                (stream_id, algorithm_id)
            )
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except Exception as e:
            logger.error(f"检查任务存在异常: {e}")
            return False
    
    def _update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        try:
            # 更新数据库
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, task_id)
            )
            conn.commit()
            conn.close()
            
            # 更新缓存
            self.task_status[task_id] = status
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = status
                
        except Exception as e:
            logger.error(f"更新任务状态异常: {e}")

def get_task_module():
    """获取任务模块实例"""
    return TaskModule.get_instance() 