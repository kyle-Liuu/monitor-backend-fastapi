"""
数据访问层测试模块
"""

import unittest
import sys
import os
import sqlite3
import tempfile
import json

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.analyzer.dal.base import BaseDAO
from app.core.analyzer.dal.stream_dao import StreamDAO

class TestBaseDAO(unittest.TestCase):
    """基础DAO测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value INTEGER,
            data TEXT
        )
        """)
        conn.commit()
        conn.close()
        
        # 初始化连接池
        BaseDAO.init_pool(self.db_path, max_connections=3)
        
        # 创建DAO实例
        self.dao = BaseDAO()
    
    def tearDown(self):
        """测试后清理"""
        # 关闭并删除临时数据库
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_execute_query(self):
        """测试查询执行"""
        # 插入测试数据
        self.dao.execute_insert(
            "INSERT INTO test_table (name, value, data) VALUES (?, ?, ?)",
            ("test1", 100, '{"key": "value1"}')
        )
        self.dao.execute_insert(
            "INSERT INTO test_table (name, value, data) VALUES (?, ?, ?)",
            ("test2", 200, '{"key": "value2"}')
        )
        
        # 执行查询
        results = self.dao.execute_query("SELECT * FROM test_table")
        
        # 验证结果
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "test1")
        self.assertEqual(results[0]["value"], 100)
        self.assertEqual(results[1]["name"], "test2")
        self.assertEqual(results[1]["value"], 200)
    
    def test_execute_update(self):
        """测试更新执行"""
        # 插入测试数据
        self.dao.execute_insert(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            ("test", 100)
        )
        
        # 执行更新
        rows_affected = self.dao.execute_update(
            "UPDATE test_table SET value = ? WHERE name = ?",
            (200, "test")
        )
        
        # 验证结果
        self.assertEqual(rows_affected, 1)
        
        # 验证数据已更新
        result = self.dao.execute_query(
            "SELECT value FROM test_table WHERE name = ?",
            ("test",)
        )
        self.assertEqual(result[0]["value"], 200)
    
    def test_execute_insert(self):
        """测试插入执行"""
        # 执行插入
        last_id = self.dao.execute_insert(
            "INSERT INTO test_table (name, value) VALUES (?, ?)",
            ("new_item", 300)
        )
        
        # 验证结果
        self.assertEqual(last_id, 1)  # 首行ID应为1
        
        # 验证数据已插入
        result = self.dao.execute_query(
            "SELECT * FROM test_table WHERE id = ?",
            (last_id,)
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "new_item")
        self.assertEqual(result[0]["value"], 300)
    
    def tearDown(self):
        """测试后清理"""
        # 关闭连接池
        BaseDAO.close_pool()
        
        # 关闭并删除临时数据库
        os.close(self.db_fd)
        os.unlink(self.db_path)

class TestStreamDAO(unittest.TestCase):
    """流数据访问对象测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE streams (
            stream_id TEXT PRIMARY KEY,
            name TEXT,
            url TEXT,
            description TEXT,
            type TEXT,
            status TEXT,
            error_message TEXT,
            enable_record INTEGER,
            record_path TEXT,
            last_online_time TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            consumers TEXT,
            frame_width INTEGER DEFAULT 0,
            frame_height INTEGER DEFAULT 0,
            fps REAL DEFAULT 0
        )
        """)
        conn.commit()
        conn.close()
        
        # 初始化连接池
        BaseDAO.init_pool(self.db_path, max_connections=3)
        
        # 创建DAO实例
        self.stream_dao = StreamDAO()
    
    def tearDown(self):
        """测试后清理"""
        # 关闭连接池
        BaseDAO.close_pool()
        
        # 关闭并删除临时数据库
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_add_stream(self):
        """测试添加流"""
        # 创建测试流数据
        stream_data = {
            "stream_id": "stream1",
            "name": "测试流",
            "url": "rtsp://localhost/test",
            "description": "测试描述",
            "type": "rtsp",
            "status": "offline"
        }
        
        # 添加流
        result = self.stream_dao.add_stream(stream_data)
        self.assertTrue(result)
        
        # 验证流已添加
        stream = self.stream_dao.get_stream_by_id("stream1")
        self.assertIsNotNone(stream)
        self.assertEqual(stream["stream_id"], "stream1")
        self.assertEqual(stream["name"], "测试流")
        self.assertEqual(stream["url"], "rtsp://localhost/test")
    
    def test_get_all_streams(self):
        """测试获取所有流"""
        # 添加多个测试流
        self.stream_dao.add_stream({
            "stream_id": "stream1",
            "name": "流1",
            "url": "rtsp://localhost/test1"
        })
        self.stream_dao.add_stream({
            "stream_id": "stream2",
            "name": "流2",
            "url": "rtsp://localhost/test2"
        })
        
        # 获取所有流
        streams = self.stream_dao.get_all_streams()
        
        # 验证结果
        self.assertEqual(len(streams), 2)
        stream_ids = [stream["stream_id"] for stream in streams]
        self.assertIn("stream1", stream_ids)
        self.assertIn("stream2", stream_ids)
    
    def test_update_stream_status(self):
        """测试更新流状态"""
        # 添加测试流
        self.stream_dao.add_stream({
            "stream_id": "stream1",
            "name": "测试流",
            "url": "rtsp://localhost/test",
            "status": "offline"
        })
        
        # 更新状态
        result = self.stream_dao.update_stream_status("stream1", "online")
        self.assertTrue(result)
        
        # 验证状态已更新
        stream = self.stream_dao.get_stream_by_id("stream1")
        self.assertEqual(stream["status"], "online")
        
        # 更新状态和错误消息
        result = self.stream_dao.update_stream_status("stream1", "error", "连接失败")
        self.assertTrue(result)
        
        # 验证状态和错误消息已更新
        stream = self.stream_dao.get_stream_by_id("stream1")
        self.assertEqual(stream["status"], "error")
        self.assertEqual(stream["error_message"], "连接失败")
    
    def test_update_consumers(self):
        """测试更新消费者"""
        # 添加测试流
        self.stream_dao.add_stream({
            "stream_id": "stream1",
            "name": "测试流",
            "url": "rtsp://localhost/test"
        })
        
        # 更新消费者列表
        consumers = ["task1", "task2", "task3"]
        result = self.stream_dao.update_consumers("stream1", consumers)
        self.assertTrue(result)
        
        # 验证消费者已更新
        stream = self.stream_dao.get_stream_by_id("stream1")
        self.assertEqual(stream["consumers"], consumers)
    
    def test_delete_stream(self):
        """测试删除流"""
        # 添加测试流
        self.stream_dao.add_stream({
            "stream_id": "stream1",
            "name": "测试流",
            "url": "rtsp://localhost/test"
        })
        
        # 确认流存在
        self.assertTrue(self.stream_dao.stream_exists("stream1"))
        
        # 删除流
        result = self.stream_dao.delete_stream("stream1")
        self.assertTrue(result)
        
        # 验证流已删除
        self.assertFalse(self.stream_dao.stream_exists("stream1"))
        self.assertIsNone(self.stream_dao.get_stream_by_id("stream1"))
    
    def test_update_stream_properties(self):
        """测试更新流属性"""
        # 添加测试流
        self.stream_dao.add_stream({
            "stream_id": "stream1",
            "name": "测试流",
            "url": "rtsp://localhost/test"
        })
        
        # 更新属性
        result = self.stream_dao.update_stream_properties("stream1", 1920, 1080, 25.0)
        self.assertTrue(result)
        
        # 验证属性已更新
        stream = self.stream_dao.get_stream_by_id("stream1")
        self.assertEqual(stream["frame_width"], 1920)
        self.assertEqual(stream["frame_height"], 1080)
        self.assertEqual(stream["fps"], 25.0)

if __name__ == "__main__":
    unittest.main() 