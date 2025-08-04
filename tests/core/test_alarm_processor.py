"""
告警处理器单元测试
测试AlarmProcessor模块的核心功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.alarm_processor import AlarmProcessor


class TestAlarmProcessor(unittest.TestCase):
    """告警处理器测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.alarm_processor = AlarmProcessor()
        
        # 创建临时数据库用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = os.path.join(self.temp_dir, 'test_alarm.db')
        
        # 创建测试数据库表
        conn = sqlite3.connect(self.temp_db)
        cursor = conn.cursor()
        
        # 创建tasks表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT,
                config TEXT,
                alarm_config TEXT
            )
        """)
        
        # 创建alarms表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alarms (
                alarm_id TEXT PRIMARY KEY,
                task_id TEXT,
                stream_id TEXT,
                label TEXT,
                bbox TEXT,
                frame_id INTEGER,
                timestamp TEXT,
                status TEXT DEFAULT 'pending',
                level TEXT DEFAULT 'warning',
                image_path TEXT,
                video_path TEXT,
                original_image TEXT,
                processed_image TEXT,
                video_clip TEXT
            )
        """)
        
        # 插入测试任务
        cursor.execute("""
            INSERT INTO tasks (task_id, name, config, alarm_config) 
            VALUES (?, ?, ?, ?)
        """, (
            "test_task_001", 
            "测试任务",
            '{"test": true}',
            '{"enabled": true, "confidence_threshold": 0.8, "pre_seconds": 5, "post_seconds": 5, "save_video": true}'
        ))
        
        conn.commit()
        conn.close()
        
        # 设置测试数据库路径（如果AlarmProcessor支持的话）
        # 注意：这里假设AlarmProcessor使用全局数据库连接
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_alarm_processor_init(self):
        """测试告警处理器初始化"""
        self.assertIsInstance(self.alarm_processor, AlarmProcessor)
        self.assertIsInstance(self.alarm_processor.cooldown_cache, dict)
    
    def test_is_in_cooldown(self):
        """测试冷却机制检查"""
        task_id = "test_task_001"
        
        # 初始状态，应该不在冷却期
        is_in_cooldown = self.alarm_processor._is_in_cooldown(task_id)
        self.assertFalse(is_in_cooldown)
        
        # 手动设置冷却期
        from datetime import datetime, timedelta
        self.alarm_processor.cooldown_cache[task_id] = datetime.now() + timedelta(seconds=60)  # 60秒后过期
        
        # 现在应该在冷却期
        is_in_cooldown = self.alarm_processor._is_in_cooldown(task_id)
        self.assertTrue(is_in_cooldown)
        
        # 设置已过期的冷却期
        self.alarm_processor.cooldown_cache[task_id] = datetime.now() - timedelta(seconds=60)  # 60秒前已过期
        
        # 现在应该不在冷却期
        is_in_cooldown = self.alarm_processor._is_in_cooldown(task_id)
        self.assertFalse(is_in_cooldown)
    
    @patch('app.core.alarm_processor.SessionLocal')
    def test_get_task_config(self, mock_session_local):
        """测试获取任务配置"""
        # 模拟数据库连接
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # 模拟查询结果
        mock_result = Mock()
        mock_result.config = '{"enabled": true, "confidence_threshold": 0.8}'
        mock_session.query().filter().first.return_value = mock_result
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            config = loop.run_until_complete(
                self.alarm_processor._get_task_config("test_task_001")
            )
            
            # 验证结果
            self.assertIsInstance(config, dict)
            self.assertTrue(config.get("enabled"))
            self.assertEqual(config.get("confidence_threshold"), 0.8)
        finally:
            loop.close()
    
    @patch('app.core.alarm_processor.SessionLocal')
    @patch('app.utils.utils.generate_unique_id')
    def test_create_alarm_record(self, mock_generate_id, mock_session_local):
        """测试创建告警记录"""
        # 模拟ID生成
        mock_generate_id.return_value = "alarm_test_001"
        
        # 模拟数据库连接
        mock_session = Mock()
        mock_session_local.return_value = mock_session
        
        # 测试数据
        detection_result = {
            "task_id": "test_task_001",
            "stream_id": "test_stream_001",
            "timestamp": "2024-12-19T10:30:00",
            "detections": [
                {"class_name": "person", "confidence": 0.85, "bbox": [100, 200, 300, 400]}
            ]
        }
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            alarm_id = loop.run_until_complete(
                self.alarm_processor._create_alarm_record("test_task_001", detection_result)
            )
            
            # 验证结果
            self.assertIsNotNone(alarm_id)
            self.assertTrue(alarm_id.startswith("alarm"))
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
        finally:
            loop.close()
    
    @patch('app.core.alarm_processor.AlarmProcessor._save_alarm_images')
    @patch('app.core.alarm_processor.AlarmProcessor._save_alarm_video')
    @patch('app.core.alarm_processor.AlarmProcessor._update_alarm_media_paths')
    def test_save_alarm_media(self, mock_update_paths, mock_save_video, mock_save_images):
        """测试保存告警媒体文件"""
        # 模拟返回值
        mock_save_images.return_value = {
            "original_image": "/path/to/original.jpg",
            "processed_image": "/path/to/processed.jpg"
        }
        mock_save_video.return_value = "/path/to/video.mp4"
        mock_update_paths.return_value = None
        
        # 测试数据
        detection_result = {
            "task_id": "test_task_001",
            "original_image": "base64_image_data",
            "processed_image": "base64_processed_data"
        }
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.alarm_processor._save_alarm_media("alarm_test_001", detection_result)
            )
            
            # 验证调用
            mock_save_images.assert_called_once()
            mock_save_video.assert_called_once()
            mock_update_paths.assert_called_once()
        finally:
            loop.close()
    
    @patch('app.core.alarm_processor.websocket_manager')
    def test_send_alarm_notification(self, mock_ws_manager):
        """测试发送告警通知"""
        # 正确设置异步mock
        async_mock = AsyncMock()
        mock_ws_manager.broadcast_alarm = async_mock
        
        # 测试数据
        from datetime import datetime
        detection_result = {
            "task_id": "test_task_001",
            "stream_id": "test_stream_001",
            "timestamp": datetime.now(),
            "detections": [{"class_name": "person", "confidence": 0.85}]
        }
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            task = loop.create_task(
                self.alarm_processor._send_alarm_notification("alarm_test_001", detection_result)
            )
            loop.run_until_complete(task)
            
            # 验证调用
            async_mock.assert_called_once()
        finally:
            loop.close()
    
    def test_get_alarm_statistics(self):
        """测试获取告警统计"""
        with patch('app.core.alarm_processor.SessionLocal') as mock_session_local:
            # 模拟数据库连接
            mock_session = Mock()
            mock_session_local.return_value = mock_session
            
            # 创建mock查询对象
            mock_query = Mock()
            mock_session.query.return_value = mock_query
            
            # 模拟查询结果
            mock_query.count.return_value = 10
            mock_query.filter.return_value.count.return_value = 3
            mock_query.with_entities.return_value.group_by.return_value.all.return_value = [
                ("warning", 7), ("error", 3)
            ]
            
            # 运行测试
            stats = self.alarm_processor.get_alarm_statistics()
            
            # 验证结果
            self.assertIsInstance(stats, dict)
            self.assertIn("total_alarms", stats)
            self.assertEqual(stats["total_alarms"], 10)
            self.assertIn("unprocessed_alarms", stats)
            self.assertIn("processed_alarms", stats)
            self.assertIn("alarm_types", stats)


class TestAlarmProcessorIntegration(unittest.TestCase):
    """告警处理器集成测试"""
    
    def setUp(self):
        """测试前设置"""
        self.alarm_processor = AlarmProcessor()
    
    @patch('app.core.alarm_processor.AlarmProcessor._should_trigger_alarm')
    @patch('app.core.alarm_processor.AlarmProcessor._create_alarm_record')
    @patch('app.core.alarm_processor.AlarmProcessor._save_alarm_media')
    @patch('app.core.alarm_processor.AlarmProcessor._send_alarm_notification')
    @patch('app.core.alarm_processor.AlarmProcessor._set_alarm_cooldown')
    def test_process_detection_result_success(self, mock_cooldown, mock_notify, 
                                            mock_save_media, mock_create_record, 
                                            mock_should_trigger):
        """测试成功处理检测结果"""
        # 模拟应该触发告警
        mock_should_trigger.return_value = (True, "confidence_threshold_exceeded")
        mock_create_record.return_value = "alarm_test_001"
        mock_save_media.return_value = None
        mock_notify.return_value = None
        mock_cooldown.return_value = None
        
        # 测试数据
        detection_result = {
            "task_id": "test_task_001",
            "stream_id": "test_stream_001",
            "detections": [{"class_name": "person", "confidence": 0.9}]
        }
        
        # 运行测试
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.alarm_processor.process_detection_result("test_task_001", detection_result)
            )
            
            # 验证所有步骤都被调用
            mock_should_trigger.assert_called_once()
            mock_create_record.assert_called_once()
            mock_save_media.assert_called_once()
            mock_notify.assert_called_once()
            mock_cooldown.assert_called_once()
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main() 