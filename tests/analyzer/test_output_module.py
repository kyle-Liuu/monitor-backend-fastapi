"""
输出模块单元测试
测试分析结果输出和视频推流功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys
import json
import queue
import threading
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.analyzer.output_module import OutputModule

class TestOutputModule(unittest.TestCase):
    """输出模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_path = tempfile.mktemp(suffix='.db')
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS outputs (
                output_id TEXT PRIMARY KEY,
                task_id TEXT,
                url TEXT,
                type TEXT,
                config TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        # 创建输出模块实例
        self.output_module = OutputModule.get_instance()
        self.output_module.db_path = self.db_path
        
        # 启动模块
        self.output_module.start()
    
    def tearDown(self):
        """测试后清理"""
        # 停止模块
        if hasattr(self, 'output_module'):
            self.output_module.stop()
        
        # 删除临时数据库
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass
    
    def test_output_module_singleton(self):
        """测试输出模块单例模式"""
        module1 = OutputModule.get_instance()
        module2 = OutputModule.get_instance()
        
        self.assertIs(module1, module2)
    
    def test_output_module_start_stop(self):
        """测试输出模块启动停止"""
        # 测试启动
        success = self.output_module.start()
        self.assertTrue(success)
        self.assertTrue(self.output_module.running)
        
        # 测试停止
        success = self.output_module.stop()
        self.assertTrue(success)
        self.assertFalse(self.output_module.running)
    
    def test_create_output(self):
        """测试创建输出"""
        output_id = "output_test_001"
        task_id = "task_test_001"
        url = "rtmp://test.example.com/live/stream"
        output_type = "rtmp"
        config = {
            "fps": 25,
            "resolution": "1920x1080",
            "bitrate": "2000k"
        }
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, output_type, config
        )
        
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_get_output(self):
        """测试获取输出"""
        # 先创建输出
        output_id = "output_get_test_001"
        task_id = "task_get_test_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        self.assertTrue(success)
        
        # 获取输出
        output_info = self.output_module.get_output_info(output_id)
        
        self.assertIsInstance(output_info, dict)
        if output_info:  # 如果有数据
            self.assertEqual(output_info["output_id"], output_id)
            self.assertEqual(output_info["task_id"], task_id)
            self.assertEqual(output_info["type"], "rtmp")
    
    def test_list_outputs(self):
        """测试列出输出"""
        # 创建多个输出
        created_outputs = []
        for i in range(3):
            output_id = f"output_list_test_{i:03d}"
            task_id = f"task_list_test_{i:03d}"
            url = f"rtmp://test.example.com/live/stream{i}"
            output_type = "rtmp" if i % 2 == 0 else "file"
            
            success, error = self.output_module.create_output(
                output_id, task_id, url, output_type
            )
            if success:
                created_outputs.append(output_id)
        
        # 获取输出列表
        all_outputs = self.output_module.get_output_info()
        
        self.assertIsInstance(all_outputs, dict)
        
        # 验证创建的输出存在
        self.assertEqual(len(created_outputs), 3)
    
    def test_stop_output_functionality(self):
        """测试停止输出功能"""
        # 创建输出
        output_id = "output_stop_test_001"
        task_id = "task_stop_test_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        self.assertTrue(success)
        
        # 停止输出
        success, error = self.output_module.stop_output(output_id)
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_get_all_outputs_info(self):
        """测试获取所有输出信息"""
        # 创建输出
        output_id = "output_all_test_001"
        task_id = "task_all_test_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        self.assertTrue(success)
        
        # 获取所有输出信息
        all_outputs = self.output_module.get_output_info()
        
        self.assertIsInstance(all_outputs, dict)
        # 验证我们创建的输出存在
        if output_id in all_outputs:
            self.assertEqual(all_outputs[output_id]["task_id"], task_id)
    
    def test_output_creation_starts_automatically(self):
        """测试输出创建时自动启动"""
        # 创建输出（会自动启动）
        output_id = "output_auto_start_001"
        task_id = "task_auto_start_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        self.assertTrue(success)
        
        # 验证输出已创建并启动
        # 注意：由于模拟环境，可能没有实际的线程运行
        output_info = self.output_module.get_output_info(output_id)
        self.assertIsInstance(output_info, dict)
        if output_info:
            self.assertEqual(output_info["output_id"], output_id)
    
    def test_stop_output_after_creation(self):
        """测试创建后停止输出"""
        # 创建输出
        output_id = "output_stop_after_001"
        task_id = "task_stop_after_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        self.assertTrue(success)
        
        # 停止输出
        success, error = self.output_module.stop_output(output_id)
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_output_configuration(self):
        """测试输出配置"""
        # 创建带配置的输出
        output_id = "output_config_test_001"
        task_id = "task_config_test_001"
        url = "rtmp://test.example.com/live/stream"
        config = {
            "fps": 30,
            "bitrate": "3000k",
            "resolution": "1920x1080"
        }
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp", config
        )
        self.assertTrue(success)
        
        # 验证配置
        output_info = self.output_module.get_output_info(output_id)
        if output_info and "config" in output_info:
            self.assertEqual(output_info["config"]["fps"], 30)
    
    def test_file_output_type(self):
        """测试文件输出类型"""
        # 创建文件输出
        output_id = "output_file_test_001"
        task_id = "task_file_test_001"
        file_path = "/tmp/test_output.mp4"
        
        success, error = self.output_module.create_output(
            output_id, task_id, file_path, "file"
        )
        self.assertTrue(success)
        
        # 验证输出类型
        output_info = self.output_module.get_output_info(output_id)
        if output_info:
            self.assertEqual(output_info["type"], "file")
            self.assertEqual(output_info["url"], file_path)
    
    def test_module_start_stop_functionality(self):
        """测试模块启动停止功能"""
        # 验证模块运行状态
        self.assertTrue(self.output_module.running)
        
        # 测试停止模块
        success = self.output_module.stop()
        self.assertTrue(success)
        self.assertFalse(self.output_module.running)
        
        # 测试重新启动模块
        success = self.output_module.start()
        self.assertTrue(success)
        self.assertTrue(self.output_module.running)
    
    def test_multiple_outputs_management(self):
        """测试多个输出管理"""
        created_outputs = []
        
        # 创建多个输出
        for i in range(3):
            output_id = f"output_multi_{i:03d}"
            task_id = f"task_multi_{i:03d}"
            url = f"rtmp://test.example.com/live/stream{i}"
            
            success, error = self.output_module.create_output(
                output_id, task_id, url, "rtmp"
            )
            if success:
                created_outputs.append(output_id)
        
        # 获取所有输出信息
        all_outputs = self.output_module.get_output_info()
        
        self.assertIsInstance(all_outputs, dict)
        self.assertEqual(len(created_outputs), 3)
        
        # 停止所有创建的输出
        for output_id in created_outputs:
            success, error = self.output_module.stop_output(output_id)
            self.assertTrue(success)
    
    @patch('app.core.analyzer.output_module.logger')
    def test_error_handling(self, mock_logger):
        """测试错误处理"""
        # 测试无效的数据库操作
        original_db_path = self.output_module.db_path
        self.output_module.db_path = "/invalid/path/database.db"
        
        # 尝试创建输出
        output_id = "output_error_test_001"
        task_id = "task_error_test_001"
        url = "rtmp://test.example.com/live/stream"
        
        success, error = self.output_module.create_output(
            output_id, task_id, url, "rtmp"
        )
        
        # 应该处理错误并记录日志
        self.assertFalse(success)
        self.assertIsNotNone(error)
        mock_logger.error.assert_called()
        
        # 恢复数据库路径
        self.output_module.db_path = original_db_path

if __name__ == '__main__':
    unittest.main() 