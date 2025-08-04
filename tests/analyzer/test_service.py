"""
分析器服务单元测试
测试分析器服务的各种功能，包括任务管理、告警事件处理等
"""

import unittest
import time
import asyncio
from unittest.mock import patch, Mock, AsyncMock
import threading
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.analyzer.analyzer_service import AnalyzerService, get_analyzer_service
from app.core.analyzer.event.event_bus import Event

class TestAnalyzerService(unittest.TestCase):
    """分析器服务测试"""
    
    def setUp(self):
        """测试前设置"""
        # 重置单例，确保每次测试都是干净的实例
        AnalyzerService._instance = None
        
        # 创建新的服务实例
        self.analyzer_service = AnalyzerService.get_instance()
        
        # 启动服务
        success = self.analyzer_service.start()
        self.assertTrue(success, "服务启动失败")
        
        # 等待服务完全启动
        time.sleep(0.1)
    
    def tearDown(self):
        """测试后清理"""
        # 停止服务
        if self.analyzer_service.running:
            self.analyzer_service.stop()
        
        # 重置单例
        AnalyzerService._instance = None
        
        # 等待清理完成
        time.sleep(0.1)
    
    def test_start_analyzer(self):
        """测试启动分析器"""
        # 服务已在setUp中启动，验证状态
        self.assertTrue(self.analyzer_service.running)
        
        # 验证各个模块的状态
        status = self.analyzer_service.get_status()
        
        # 验证基本状态信息
        self.assertIn("status", status)
        self.assertEqual(status["status"], "running")
        
        # 验证模块状态
        self.assertIn("modules", status)
        modules = status["modules"]
        
        # 验证关键模块已启动
        self.assertTrue(modules.get("stream", False))
        self.assertTrue(modules.get("algorithm", False))
        self.assertTrue(modules.get("task", False))
    
    def test_stop_analyzer(self):
        """测试停止分析器"""
        # 停止服务
        success = self.analyzer_service.stop()
        self.assertTrue(success, "服务停止失败")
        
        # 验证服务已停止
        self.assertFalse(self.analyzer_service.running)
    
    def test_get_status(self):
        """测试获取状态"""
        status = self.analyzer_service.get_status()
        
        # 验证状态信息完整性
        required_keys = ["status", "modules", "streams", "algorithms", "tasks"]
        for key in required_keys:
            self.assertIn(key, status, f"状态信息缺少 {key}")
        
        # 验证运行状态
        self.assertEqual(status["status"], "running")
        
        # 验证模块状态
        modules = status["modules"]
        self.assertIsInstance(modules, dict)
        
        # 验证流、算法、任务统计
        self.assertIsInstance(status["streams"], int)
        self.assertIsInstance(status["algorithms"], int)
        self.assertIsInstance(status["tasks"], int)
    
    def test_create_task(self):
        """测试创建任务"""
        # 模拟task_module的检查方法
        self.analyzer_service.task_module._check_stream_exists = Mock(return_value=True)
        self.analyzer_service.task_module._check_algorithm_exists = Mock(return_value=True)
        self.analyzer_service.task_module._check_task_exists = Mock(return_value=False)
        
        # 模拟stream_module和algorithm_module的get_info方法（analyzer_service会调用）
        self.analyzer_service.stream_module.get_stream_info = Mock(return_value={
            "stream_id": "test_stream_001",
            "name": "测试流",
            "url": "rtsp://127.0.0.1/live/test"
        })
        
        self.analyzer_service.algorithm_module.get_algorithm_info = Mock(return_value={
            "algo_id": "test_algo_001",
            "name": "测试算法"
        })
        
        # 创建任务参数
        stream_id = "test_stream_001"
        algorithm_id = "test_algo_001"
        task_name = "测试任务"
        
        # 执行创建任务
        success, message, task_id = self.analyzer_service.create_task(
            stream_id=stream_id,
            algorithm_id=algorithm_id,
            name=task_name
        )
        
        # 验证创建成功
        self.assertTrue(success, f"创建任务失败: {message}")
        self.assertIsNotNone(task_id)
        self.assertTrue(task_id.startswith("task"))
    
    def test_start_task(self):
        """测试启动任务"""
        # 使用不存在的任务ID测试启动失败的情况
        success, message = self.analyzer_service.start_task("nonexistent_task")
        self.assertFalse(success)
        self.assertIn("任务不存在", message)
    
    def test_stop_task(self):
        """测试停止任务"""
        # 使用不存在的任务ID测试停止失败的情况
        success, message = self.analyzer_service.stop_task("nonexistent_task")
        self.assertFalse(success)
        self.assertIn("任务不存在", message)
    
    def test_delete_task(self):
        """测试删除任务"""
        # 使用不存在的任务ID测试删除失败的情况
        success, message = self.analyzer_service.delete_task("nonexistent_task")
        self.assertFalse(success)
        self.assertIn("任务不存在", message)
    
    @patch('app.core.alarm_processor.alarm_processor.process_detection_result')
    def test_alarm_event_handling(self, mock_process_alarm):
        """测试告警事件处理（新增功能）"""
        # 正确设置异步mock
        async_mock = AsyncMock()
        mock_process_alarm.return_value = async_mock
        
        # 模拟告警事件数据
        from app.core.analyzer.event.event_bus import Event
        alarm_event_data = {
            "alarm_id": "alarm_test_001",
            "task_id": "test_task_001", 
            "stream_id": "test_stream_001",
            "timestamp": "2024-12-19T10:30:00",
            "detection_result": {
                "detections": [
                    {"class_name": "person", "confidence": 0.85}
                ]
            },
            "original_image": "base64_image_data",
            "processed_image": "base64_processed_data"
        }
        
        # 创建告警事件
        alarm_event = Event("alarm.triggered", "test_analyzer", alarm_event_data)
        
        # 使用patch来模拟asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            # 创建一个已完成的异步任务mock
            mock_task = Mock()
            mock_task.done.return_value = True
            mock_task.result.return_value = None
            mock_create_task.return_value = mock_task
            
            # 触发事件处理
            self.analyzer_service._handle_alarm(alarm_event)
            
            # 验证asyncio.create_task被调用
            mock_create_task.assert_called_once()
    
    def test_alarm_event_missing_task_id(self):
        """测试缺少task_id的告警事件处理"""
        from app.core.analyzer.event.event_bus import Event
        
        # 模拟缺少task_id的告警事件
        alarm_event_data = {
            "alarm_id": "alarm_test_002",
            "stream_id": "test_stream_001",
            "detection_result": {
                "detections": [{"class_name": "car", "confidence": 0.7}]
            }
            # 注意：故意不包含task_id
        }
        
        alarm_event = Event("alarm.triggered", "test_analyzer", alarm_event_data)
        
        # 这应该能够优雅地处理，不抛出异常
        try:
            self.analyzer_service._handle_alarm(alarm_event)
            # 如果没有抛出异常，测试通过
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"处理缺少task_id的告警事件时抛出异常: {e}")
    
    @patch('app.core.alarm_processor.alarm_processor.process_detection_result')
    def test_alarm_event_error_handling(self, mock_process_alarm):
        """测试告警事件错误处理"""
        # 设置异步mock抛出异常
        async_mock = AsyncMock(side_effect=Exception("处理异常"))
        mock_process_alarm.return_value = async_mock
        
        # 模拟告警事件数据
        from app.core.analyzer.event.event_bus import Event
        alarm_event_data = {
            "alarm_id": "alarm_test_002",
            "task_id": "test_task_002"
        }
        
        # 创建告警事件
        alarm_event = Event("alarm.triggered", "test_analyzer", alarm_event_data)
        
        # 使用patch来模拟asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            # 创建一个抛出异常的任务mock
            mock_task = Mock()
            mock_task.done.return_value = True
            mock_task.exception.return_value = Exception("处理异常")
            mock_create_task.return_value = mock_task
            
            # 触发事件处理（应该不抛出异常）
            try:
                self.analyzer_service._handle_alarm(alarm_event)
            except Exception as e:
                self.fail(f"事件处理不应该抛出异常: {e}")
            
            # 验证asyncio.create_task被调用
            mock_create_task.assert_called_once()

if __name__ == '__main__':
    unittest.main() 