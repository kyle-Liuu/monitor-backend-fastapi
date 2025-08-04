"""
任务模块单元测试
测试视频分析任务管理功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.analyzer.task_module import get_task_module

class TestTaskModule(unittest.TestCase):
    """任务模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_path = tempfile.mktemp(suffix='.db')
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建流表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS streams (
                stream_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                description TEXT,
                type TEXT DEFAULT 'rtsp',
                status TEXT DEFAULT 'offline',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建算法表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithms (
                algo_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT,
                description TEXT,
                type TEXT,
                path TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        # 插入测试数据
        cursor.execute("""
            INSERT OR REPLACE INTO streams (stream_id, name, url, description, type, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("test_stream_001", "测试流", "rtsp://127.0.0.1/live/test", "测试流描述", "rtsp", "offline"))
        
        cursor.execute("""
            INSERT OR REPLACE INTO algorithms (algo_id, name, version, description, type, path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("test_algo_001", "测试算法", "1.0", "测试算法描述", "detection", "/path/to/algo", "active"))
        
        conn.commit()
        conn.close()
        
        # 获取任务模块实例并设置数据库路径
        self.task_module = get_task_module()
        self.task_module.db_path = self.db_path
        
        # 启动事件总线
        from app.core.analyzer.event_bus import get_event_bus
        self.event_bus = get_event_bus()
        self.event_bus.start()
        
        self.task_module.running = True
    
    def tearDown(self):
        """测试后清理"""
        # 停止事件总线
        if hasattr(self, 'event_bus'):
            self.event_bus.stop()
        
        # 删除临时数据库
        import os
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass
    
    def test_create_task(self):
        """测试创建任务"""
        result = self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务",
            description="测试任务描述",
            config={"param1": "value1"},
            alarm_config={"threshold": 0.8}
        )
        
        success, message, task_id = result
        self.assertTrue(success)
        self.assertIsNotNone(task_id)
        
        # 验证任务已创建
        task_info = self.task_module.get_task_info(task_id)
        self.assertIsNotNone(task_info)
        self.assertEqual(task_info["name"], "测试任务")
        self.assertEqual(task_info["stream_id"], "test_stream_001")
        self.assertEqual(task_info["algorithm_id"], "test_algo_001")
    
    def test_get_task_by_id(self):
        """测试根据ID获取任务"""
        # 先创建一个任务
        success, message, task_id = self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务"
        )
        
        # 获取任务
        task_info = self.task_module.get_task_info(task_id)
        
        self.assertIsNotNone(task_info)
        self.assertEqual(task_info["name"], "测试任务")
        self.assertEqual(task_info["stream_id"], "test_stream_001")
    
    def test_get_tasks_by_stream(self):
        """测试根据流ID获取任务"""
        # 先创建一个任务
        self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务"
        )
        
        # 获取流相关的任务
        tasks = self.task_module.get_tasks_by_stream("test_stream_001")
        
        self.assertIsInstance(tasks, list)
        self.assertGreater(len(tasks), 0)
        self.assertEqual(tasks[0]["stream_id"], "test_stream_001")
    
    def test_update_task_progress(self):
        """测试更新任务进度"""
        # 先创建一个任务
        success, message, task_id = self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务"
        )
        
        # 更新任务进度
        success, message = self.task_module.update_task_progress(
            task_id=task_id,
            frame_count=100,
            last_frame_time=1234567890.0
        )
        
        self.assertTrue(success)
        
        # 验证进度已更新
        task_info = self.task_module.get_task_info(task_id)
        self.assertEqual(task_info["frame_count"], 100)
        self.assertEqual(task_info["last_frame_time"], 1234567890.0)
    
    def test_update_task_status(self):
        """测试更新任务状态"""
        # 先创建一个任务
        success, message, task_id = self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务"
        )
        
        # 启动任务
        success, message = self.task_module.start_task(task_id)
        self.assertTrue(success)
        
        # 验证任务状态
        task_info = self.task_module.get_task_info(task_id)
        self.assertEqual(task_info["status"], "running")
    
    def test_delete_task(self):
        """测试删除任务"""
        # 先创建一个任务
        success, message, task_id = self.task_module.create_task(
            stream_id="test_stream_001",
            algorithm_id="test_algo_001",
            name="测试任务"
        )
        
        # 删除任务
        success, message = self.task_module.delete_task(task_id)
        self.assertTrue(success)
        
        # 验证任务已删除
        task_info = self.task_module.get_task_info(task_id)
        self.assertEqual(task_info, {})

if __name__ == "__main__":
    unittest.main() 