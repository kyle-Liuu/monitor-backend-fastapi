"""
告警模块单元测试
测试告警处理和管理功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys
import json
import time
from datetime import datetime
from unittest.mock import Mock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.analyzer.alarm_module import AlarmModule

class TestAlarmModule(unittest.TestCase):
    """告警模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_path = tempfile.mktemp(suffix='.db')
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alarms (
                alarm_id TEXT PRIMARY KEY,
                task_id TEXT,
                stream_id TEXT,
                label TEXT,
                confidence REAL,
                bbox TEXT,
                frame_id INTEGER,
                timestamp TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'new',
                level TEXT,
                image_path TEXT,
                video_path TEXT
            )
        """)
        
        conn.commit()
        conn.close()
        
        # 创建告警模块实例
        self.alarm_module = AlarmModule.get_instance()
        self.alarm_module.db_path = self.db_path
        
        # 启动模块
        self.alarm_module.start()
    
    def tearDown(self):
        """测试后清理"""
        # 停止模块
        if hasattr(self, 'alarm_module'):
            self.alarm_module.stop()
        
        # 删除临时数据库
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass
    
    def test_alarm_module_singleton(self):
        """测试告警模块单例模式"""
        module1 = AlarmModule.get_instance()
        module2 = AlarmModule.get_instance()
        
        self.assertIs(module1, module2)
    
    def test_alarm_module_start_stop(self):
        """测试告警模块启动停止"""
        # 测试启动
        success = self.alarm_module.start()
        self.assertTrue(success)
        self.assertTrue(self.alarm_module.running)
        
        # 测试停止
        success = self.alarm_module.stop()
        self.assertTrue(success)
        self.assertFalse(self.alarm_module.running)
    
    def test_create_alarm_internal(self):
        """测试内部告警创建"""
        # 创建模拟告警数据
        alarm_data = {
            "alarm_id": "alarm_test_001",
            "task_id": "test_task_001",
            "stream_id": "test_stream_001", 
            "label": "person",
            "confidence": 0.85,
            "bbox": [100, 200, 300, 400],
            "frame_id": 12345,
            "timestamp": "2024-12-19T10:30:00",
            "created_at": time.time(),
            "status": "new",
            "level": "high"
        }
        
        # 测试内部保存方法
        success = self.alarm_module._save_alarm(alarm_data)
        
        self.assertTrue(success)
        
        # 验证能够获取创建的告警
        alarms = self.alarm_module.get_alarms({"alarm_id": "alarm_test_001"})
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0]["alarm_id"], "alarm_test_001")
    
    def test_get_alarm(self):
        """测试获取告警"""
        # 先创建告警
        alarm_data = {
            "alarm_id": "alarm_test_002",
            "task_id": "test_task_001",
            "stream_id": "test_stream_001",
            "label": "car",
            "confidence": 0.75,
            "bbox": [50, 100, 250, 300],
            "frame_id": 12346,
            "timestamp": "2024-12-19T10:31:00",
            "created_at": time.time(),
            "status": "new",
            "level": "medium"
        }
        
        success = self.alarm_module._save_alarm(alarm_data)
        self.assertTrue(success)
        
        # 获取告警
        alarms = self.alarm_module.get_alarms({"alarm_id": "alarm_test_002"})
        
        self.assertEqual(len(alarms), 1)
        alarm_info = alarms[0]
        self.assertEqual(alarm_info["alarm_id"], "alarm_test_002")
        self.assertEqual(alarm_info["task_id"], "test_task_001")
        self.assertEqual(alarm_info["label"], "car")
    
    def test_list_alarms(self):
        """测试列出告警"""
        # 创建多个告警
        for i in range(3):
            alarm_data = {
                "alarm_id": f"alarm_test_{i:03d}",
                "task_id": f"test_task_{i:03d}",
                "stream_id": "test_stream_001",
                "label": "person",
                "confidence": 0.7 + i * 0.1,
                "bbox": [100, 200, 300, 400],
                "frame_id": 12347 + i,
                "timestamp": f"2024-12-19T10:3{i}:00",
                "created_at": time.time() + i,
                "status": "new",
                "level": "medium"
            }
            self.alarm_module._save_alarm(alarm_data)
        
        # 获取告警列表
        alarms = self.alarm_module.get_alarms()
        
        self.assertIsInstance(alarms, list)
        self.assertGreaterEqual(len(alarms), 3)  # 可能有之前测试创建的告警
        
        # 验证告警数据结构
        for alarm in alarms:
            self.assertIn("alarm_id", alarm)
            self.assertIn("task_id", alarm)
            self.assertIn("label", alarm)
    
    def test_list_alarms_with_filter(self):
        """测试带过滤条件的告警列表"""
        # 创建不同类型的告警
        alarm_data_person = {
            "alarm_id": "alarm_filter_001",
            "task_id": "test_task_filter_001",
            "stream_id": "test_stream_001",
            "label": "person",
            "confidence": 0.85,
            "bbox": [100, 200, 300, 400],
            "frame_id": 12350,
            "timestamp": "2024-12-19T11:00:00",
            "created_at": time.time(),
            "status": "new",
            "level": "high"
        }
        
        alarm_data_car = {
            "alarm_id": "alarm_filter_002",
            "task_id": "test_task_filter_002",
            "stream_id": "test_stream_002",
            "label": "car",
            "confidence": 0.75,
            "bbox": [50, 100, 250, 300],
            "frame_id": 12351,
            "timestamp": "2024-12-19T11:01:00",
            "created_at": time.time(),
            "status": "new",
            "level": "medium"
        }
        
        self.alarm_module._save_alarm(alarm_data_person)
        self.alarm_module._save_alarm(alarm_data_car)
        
        # 按标签过滤
        person_alarms = self.alarm_module.get_alarms({"label": "person"})
        self.assertGreaterEqual(len(person_alarms), 1)
        person_alarm = next((a for a in person_alarms if a["alarm_id"] == "alarm_filter_001"), None)
        self.assertIsNotNone(person_alarm)
        self.assertEqual(person_alarm["label"], "person")
        
        # 按任务ID过滤
        task_alarms = self.alarm_module.get_alarms({"task_id": "test_task_filter_001"})
        self.assertEqual(len(task_alarms), 1)
        self.assertEqual(task_alarms[0]["task_id"], "test_task_filter_001")
    
    def test_update_alarm_status(self):
        """测试更新告警状态"""
        # 创建告警
        alarm_data = {
            "alarm_id": "alarm_status_001",
            "task_id": "test_task_status_001",
            "stream_id": "test_stream_001",
            "label": "bicycle",
            "confidence": 0.80,
            "bbox": [75, 150, 275, 350],
            "frame_id": 12355,
            "timestamp": "2024-12-19T11:05:00",
            "created_at": time.time(),
            "status": "new",
            "level": "medium"
        }
        
        success = self.alarm_module._save_alarm(alarm_data)
        self.assertTrue(success)
        
        # 更新状态为已处理
        success = self.alarm_module.update_alarm_status("alarm_status_001", "processed")
        self.assertTrue(success)
        
        # 验证状态更新
        alarms = self.alarm_module.get_alarms({"alarm_id": "alarm_status_001"})
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0]["status"], "processed")
    
    def test_delete_alarm(self):
        """测试删除告警"""
        # 创建告警
        alarm_data = {
            "alarm_id": "alarm_delete_001",
            "task_id": "test_task_delete_001",
            "stream_id": "test_stream_001",
            "label": "truck",
            "confidence": 0.90,
            "bbox": [125, 250, 425, 550],
            "frame_id": 12360,
            "timestamp": "2024-12-19T11:10:00",
            "created_at": time.time(),
            "status": "new",
            "level": "high"
        }
        
        success = self.alarm_module._save_alarm(alarm_data)
        self.assertTrue(success)
        
        # 验证告警存在
        alarms_before = self.alarm_module.get_alarms({"alarm_id": "alarm_delete_001"})
        self.assertEqual(len(alarms_before), 1)
        
        # 删除告警
        success = self.alarm_module.delete_alarm("alarm_delete_001")
        self.assertTrue(success)
        
        # 验证告警已删除
        alarms_after = self.alarm_module.get_alarms({"alarm_id": "alarm_delete_001"})
        self.assertEqual(len(alarms_after), 0)
    
    def test_get_alarm_statistics(self):
        """测试获取告警统计（通过查询实现）"""
        # 创建不同状态的告警
        for i in range(5):
            alarm_data = {
                "alarm_id": f"alarm_stats_{i:03d}",
                "task_id": f"test_task_stats_{i:03d}",
                "stream_id": "test_stream_stats",
                "label": "motorbike",
                "confidence": 0.7 + i * 0.05,
                "bbox": [100, 200, 300, 400],
                "frame_id": 12365 + i,
                "timestamp": f"2024-12-19T11:1{i}:00",
                "created_at": time.time() + i * 10,
                "status": "new",
                "level": "high" if i % 2 == 0 else "medium"
            }
            success = self.alarm_module._save_alarm(alarm_data)
            self.assertTrue(success)
            
            # 处理部分告警
            if i < 3:
                self.alarm_module.update_alarm_status(f"alarm_stats_{i:03d}", "processed")
        
        # 通过查询获取统计信息
        all_stats_alarms = self.alarm_module.get_alarms({"task_id": "test_task_stats_000"}) + \
                          self.alarm_module.get_alarms({"task_id": "test_task_stats_001"}) + \
                          self.alarm_module.get_alarms({"task_id": "test_task_stats_002"}) + \
                          self.alarm_module.get_alarms({"task_id": "test_task_stats_003"}) + \
                          self.alarm_module.get_alarms({"task_id": "test_task_stats_004"})
        
        processed_count = len([a for a in all_stats_alarms if a["status"] == "processed"])
        new_count = len([a for a in all_stats_alarms if a["status"] == "new"])
        
        self.assertEqual(len(all_stats_alarms), 5)
        self.assertEqual(processed_count, 3)
        self.assertEqual(new_count, 2)
    
    @patch('app.core.analyzer.alarm_module.logger')
    def test_error_handling(self, mock_logger):
        """测试错误处理"""
        # 测试无效的数据库操作
        original_db_path = self.alarm_module.db_path
        self.alarm_module.db_path = "/invalid/path/database.db"
        
        # 尝试查询告警（应该失败）
        alarms = self.alarm_module.get_alarms({"alarm_id": "nonexistent"})
        
        # 应该处理错误并记录日志
        self.assertEqual(alarms, [])  # 错误时应该返回空列表
        mock_logger.error.assert_called()
        
        # 恢复数据库路径
        self.alarm_module.db_path = original_db_path

if __name__ == '__main__':
    unittest.main() 