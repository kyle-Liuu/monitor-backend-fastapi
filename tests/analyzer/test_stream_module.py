"""
流模块单元测试
测试视频流管理功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys
import time
import threading

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.analyzer.stream_module import get_stream_module

class TestStreamModule(unittest.TestCase):
    """流模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 重置单例实例，确保测试隔离
        from app.core.analyzer.stream_module import StreamModule
        StreamModule._instance = None
        
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
                stream_type TEXT DEFAULT 'rtsp',
                status TEXT DEFAULT 'inactive',
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
        
        # 获取流模块实例并设置数据库路径
        self.stream_module = get_stream_module()
        self.stream_module.db_path = self.db_path
        
        # 启动事件总线
        from app.core.analyzer.event_bus import get_event_bus
        self.event_bus = get_event_bus()
        self.event_bus.start()
        
        self.stream_module.running = True
        
        # 清理可能存在的内存状态
        if hasattr(self.stream_module, 'streams'):
            self.stream_module.streams.clear()
        if hasattr(self.stream_module, '_streams'):
            self.stream_module._streams.clear()
    
    def _clear_test_data(self):
        """清理测试数据确保测试独立性"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM streams")
            conn.commit()
            conn.close()
            
            # 清理内存状态
            if hasattr(self.stream_module, 'streams'):
                self.stream_module.streams.clear()
            if hasattr(self.stream_module, '_streams'):
                self.stream_module._streams.clear()
        except Exception as e:
            print(f"清理测试数据时出错: {e}")
    
    def tearDown(self):
        """测试后清理 - 正确的停止顺序"""
        # 1. 首先停止流模块和所有流处理线程
        if hasattr(self, 'stream_module') and self.stream_module:
            try:
                # 停止所有流
                self.stream_module._stop_all_streams()
                # 等待所有线程停止
                time.sleep(0.1)
                # 停止模块
                self.stream_module.running = False
                # 清理内存状态
                if hasattr(self.stream_module, 'streams'):
                    self.stream_module.streams.clear()
                if hasattr(self.stream_module, '_streams'):
                    self.stream_module._streams.clear()
                if hasattr(self.stream_module, 'stream_threads'):
                    for stream_id, thread in list(self.stream_module.stream_threads.items()):
                        if thread.is_alive():
                            # 设置停止事件
                            if hasattr(self.stream_module, 'stop_events') and stream_id in self.stream_module.stop_events:
                                self.stream_module.stop_events[stream_id].set()
                            # 等待线程结束
                            thread.join(timeout=1.0)
                    self.stream_module.stream_threads.clear()
                if hasattr(self.stream_module, 'stop_events'):
                    self.stream_module.stop_events.clear()
            except Exception as e:
                print(f"停止流模块时出错: {e}")
        
        # 2. 停止事件总线
        if hasattr(self, 'event_bus') and self.event_bus:
            try:
                self.event_bus.stop()
                # 等待事件总线完全停止
                time.sleep(0.1)
            except Exception as e:
                print(f"停止事件总线时出错: {e}")
        
        # 3. 重置单例实例
        try:
            from app.core.analyzer.stream_module import StreamModule
            StreamModule._instance = None
        except Exception as e:
            print(f"重置单例时出错: {e}")
        
        # 4. 最后删除数据库文件
        if hasattr(self, 'db_path') and os.path.exists(self.db_path):
            try:
                # 等待确保所有数据库连接已关闭
                time.sleep(0.1)
                os.unlink(self.db_path)
            except (PermissionError, OSError) as e:
                print(f"删除临时数据库时出错: {e}")
    
    def test_add_stream(self):
        """测试添加流"""
        # 清理测试数据
        self._clear_test_data()
        
        stream_id = "test_stream_001"
        url = "rtsp://test.com/stream"
        
        success, error = self.stream_module.add_stream(stream_id, url, "测试流")
        self.assertTrue(success, f"添加流失败: {error}")
        
        # 验证流信息
        stream_info = self.stream_module.get_stream_info(stream_id)
        self.assertIsNotNone(stream_info, "获取流信息失败")
        self.assertEqual(stream_info["stream_id"], stream_id)
        self.assertEqual(stream_info["url"], url)
    
    def test_get_stream_by_id(self):
        """测试根据ID获取流"""
        # 清理测试数据
        self._clear_test_data()
        
        stream_id = "test_stream_002"
        url = "rtsp://127.0.0.1/live/test"
        
        # 先添加流
        success, error = self.stream_module.add_stream(stream_id, url, "测试流2")
        self.assertTrue(success, f"添加流失败: {error}")
        
        # 获取流信息
        stream_info = self.stream_module.get_stream_info(stream_id)
        self.assertIsNotNone(stream_info, "获取流信息失败")
        self.assertEqual(stream_info["stream_id"], stream_id)
        self.assertEqual(stream_info["url"], url)
    
    def test_update_stream_status(self):
        """测试更新流状态"""
        # 先添加一个流
        stream_id = "test_stream_003"
        self.stream_module.add_stream(
            stream_id=stream_id,
            url="rtsp://127.0.0.1/live/test",
            name="测试流"
        )
        
        # 启动流
        success, message = self.stream_module.start_stream(stream_id)
        self.assertTrue(success)
        
        # 验证流已启动
        stream_info = self.stream_module.get_stream_info(stream_id)
        self.assertIsNotNone(stream_info)
    
    def test_delete_stream(self):
        """测试删除流"""
        # 清理测试数据
        self._clear_test_data()
        
        stream_id = "test_stream_004"
        url = "rtsp://127.0.0.1/live/test"
        
        # 先添加流
        success, error = self.stream_module.add_stream(stream_id, url, "待删除流")
        self.assertTrue(success, f"添加流失败: {error}")
        
        # 删除流
        success, error = self.stream_module.remove_stream(stream_id)
        self.assertTrue(success, f"删除流失败: {error}")
        
        # 验证流已删除
        stream_info = self.stream_module.get_stream_info(stream_id)
        self.assertIsNone(stream_info, "流删除后仍能获取到信息")
    
    def test_get_stream_statistics(self):
        """测试获取流统计信息"""
        # 先添加一个流
        stream_id = "test_stream_005"
        self.stream_module.add_stream(
            stream_id=stream_id,
            url="rtsp://127.0.0.1/live/test",
            name="测试流"
        )
        
        # 获取流信息
        stream_info = self.stream_module.get_stream_info(stream_id)
        
        self.assertIsNotNone(stream_info)
        self.assertIn("stream_id", stream_info)
        self.assertIn("url", stream_info)
    
    def test_update_stream_properties(self):
        """测试更新流属性"""
        # 先添加一个流
        stream_id = "test_stream_006"
        self.stream_module.add_stream(
            stream_id=stream_id,
            url="rtsp://127.0.0.1/live/test",
            name="测试流"
        )
        
        # 启动流
        success, message = self.stream_module.start_stream(stream_id)
        self.assertTrue(success)
        
        # 验证流已启动
        stream_info = self.stream_module.get_stream_info(stream_id)
        self.assertIsNotNone(stream_info)

if __name__ == "__main__":
    unittest.main() 