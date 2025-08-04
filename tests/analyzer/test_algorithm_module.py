"""
算法模块单元测试
测试算法管理功能
"""

import unittest
import tempfile
import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.analyzer.algorithm_module import get_algorithm_module

class TestAlgorithmModule(unittest.TestCase):
    """算法模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建临时数据库
        self.db_path = tempfile.mktemp(suffix='.db')
        
        # 创建测试表
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建算法表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS algorithms (
                algo_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT,
                description TEXT,
                package_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                author TEXT,
                enabled INTEGER,
                algorithm_type TEXT,
                status TEXT,
                device_type TEXT
            )
        """)
        # 插入测试数据
        cursor.execute("""
            INSERT OR REPLACE INTO algorithms (algo_id, name, version, description, package_name, created_at, updated_at, author, enabled, algorithm_type, status, device_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "test_algo_001", "测试算法", "1.0", "测试算法描述", "algocf6c488d", "2025-07-28 08:00:00", "2025-07-28 08:00:00", "测试作者", 1, "yolov8", "active", "cpu,gpu"
        ))
        
        conn.commit()
        conn.close()
        
        # 获取算法模块实例并设置数据库路径
        self.algorithm_module = get_algorithm_module()
        self.algorithm_module.db_path = self.db_path
        self.algorithm_module.running = True
    
    def tearDown(self):
        """测试后清理"""
        # 删除临时数据库
        import os
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_get_algorithm_info(self):
        """测试获取算法信息"""
        # 获取单个算法信息
        algo_info = self.algorithm_module.get_algorithm_info("test_algo_001")
        
        self.assertIsNotNone(algo_info)
        self.assertEqual(algo_info["name"], "测试算法")
        self.assertEqual(algo_info["author"], "测试作者")
        self.assertEqual(algo_info["status"], "active")
    
    def test_get_algorithm_path(self):
        """测试获取算法路径"""
        path = self.algorithm_module.get_algorithm_path("test_algo_001")
        
        self.assertIsNotNone(path)
        # 检查路径是否包含算法包名
        self.assertIn("algocf6c488d", path)
    
    def test_get_algorithm_info_all(self):
        """测试获取所有算法信息"""
        # 获取所有算法信息
        all_algo_info = self.algorithm_module.get_algorithm_info()
        
        self.assertIsInstance(all_algo_info, dict)
        self.assertIn("test_algo_001", all_algo_info)
    
    def test_algorithm_exists(self):
        """测试算法存在性检查"""
        # 检查存在的算法
        path = self.algorithm_module.get_algorithm_path("test_algo_001")
        self.assertIsNotNone(path)
        
        # 检查不存在的算法
        path = self.algorithm_module.get_algorithm_path("non_existent_algo")
        self.assertIsNone(path)
    
    def test_algorithm_status(self):
        """测试算法状态"""
        # 获取算法信息
        algo_info = self.algorithm_module.get_algorithm_info("test_algo_001")
        
        self.assertEqual(algo_info["status"], "active")
    
    def test_algorithm_metadata(self):
        """测试算法元数据"""
        # 获取算法信息
        algo_info = self.algorithm_module.get_algorithm_info("test_algo_001")
        
        self.assertEqual(algo_info["algorithm_type"], "yolov8")
        self.assertEqual(algo_info["device_type"], "cpu,gpu")

if __name__ == "__main__":
    unittest.main() 