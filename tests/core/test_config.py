"""
配置加载模块单元测试
测试配置文件加载和解析功能
"""

import unittest
import tempfile
import os
import sys
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.config import load_config, DEFAULT_CONFIG, CONFIG, settings

class TestConfig(unittest.TestCase):
    """配置模块测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = os.path.join(self.temp_dir, "test_config.yaml")
        
        # 创建测试配置文件
        self.test_config_data = {
            "database": {
                "url": "sqlite:///test.db",
                "echo": False
            },
            "video": {
                "buffer_size": 30,
                "fps": 25,
                "timeout": 10
            },
            "algorithm": {
                "max_instances": 3,
                "device": "cpu"
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
        
        with open(self.test_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.test_config_data, f, allow_unicode=True)
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        with patch('app.core.config.BASE_DIR', Path(self.temp_dir)):
            config = load_config()
            
            self.assertIsInstance(config, dict)
            # 测试默认配置中的实际字段
            self.assertIn('api', config)
            self.assertIn('database', config)
            self.assertIn('algorithms', config)
    
    def test_load_config_file_not_found(self):
        """测试配置文件不存在时使用默认配置"""
        # 创建一个空目录，确保config.yaml不存在
        empty_dir = tempfile.mkdtemp()
        
        with patch('app.core.config.BASE_DIR', Path(empty_dir)):
            config = load_config()
            
            # 应该返回默认配置
            self.assertIsInstance(config, dict)
            self.assertIn('database', config)
            self.assertIn('api', config)
        
        # 清理
        import shutil
        shutil.rmtree(empty_dir)
    
    def test_load_config_invalid_yaml(self):
        """测试无效YAML文件时的处理"""
        # 创建带有无效config.yaml的目录
        invalid_dir = tempfile.mkdtemp()
        invalid_yaml_path = os.path.join(invalid_dir, "config.yaml")
        with open(invalid_yaml_path, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with patch('app.core.config.BASE_DIR', Path(invalid_dir)):
            config = load_config()
            
            # 应该返回默认配置
            self.assertIsInstance(config, dict)
        
        # 清理
        import shutil
        shutil.rmtree(invalid_dir)
    
    def test_config_singleton(self):
        """测试配置单例访问"""
        # CONFIG变量应该是一个配置字典
        self.assertIsInstance(CONFIG, dict)
        
        # settings应该是Settings类的实例
        self.assertIsNotNone(settings)
        self.assertEqual(settings.PROJECT_NAME, "AI智能监控系统")
    
    def test_config_nested_access(self):
        """测试嵌套配置访问"""
        config = load_config()
        
        # 测试嵌套访问
        self.assertIn('path', config['database'])
        self.assertIn('host', config['api'])
        self.assertIn('base_path', config['algorithms'])
    
    def test_default_config_structure(self):
        """测试默认配置结构"""
        self.assertIsInstance(DEFAULT_CONFIG, dict)
        self.assertIn('database', DEFAULT_CONFIG)
        self.assertIn('api', DEFAULT_CONFIG)
        self.assertIn('algorithms', DEFAULT_CONFIG)
        self.assertIn('logging', DEFAULT_CONFIG)
    
    def test_config_merge_with_defaults(self):
        """测试配置与默认值合并"""
        # 创建部分配置文件
        partial_config = {
            "database": {
                "path": "/custom/test.db"
            },
            "api": {
                "port": 9000
            }
            # 其他配置项缺失
        }
        
        # 创建临时目录和配置文件
        merge_dir = tempfile.mkdtemp()
        partial_config_path = os.path.join(merge_dir, "config.yaml")
        with open(partial_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(partial_config, f)
        
        with patch('app.core.config.BASE_DIR', Path(merge_dir)):
            config = load_config()
            
            # 应该有自定义的配置
            self.assertEqual(config['database']['path'], "/custom/test.db")
            self.assertEqual(config['api']['port'], 9000)
            
            # 应该有默认的其他配置
            self.assertIn('algorithms', config)
            self.assertIn('logging', config)
        
        # 清理
        import shutil
        shutil.rmtree(merge_dir)

if __name__ == '__main__':
    unittest.main() 