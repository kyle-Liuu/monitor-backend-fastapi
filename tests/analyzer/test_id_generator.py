"""
ID生成器测试模块
"""

import unittest
import sys
import os
import re

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.analyzer.utils.id_generator import (
    generate_unique_id, generate_uuid, generate_timestamp_id
)

class TestIDGenerator(unittest.TestCase):
    """ID生成器测试类"""
    
    def test_generate_unique_id(self):
        """测试唯一ID生成"""
        # 测试默认长度
        id1 = generate_unique_id()
        id2 = generate_unique_id()
        
        self.assertEqual(len(id1), 9)  # "id" + 7位随机字符
        self.assertEqual(len(id2), 9)
        self.assertNotEqual(id1, id2)
        
        # 测试自定义前缀和长度
        id3 = generate_unique_id("stream", 10)
        self.assertEqual(len(id3), 16)  # "stream" + 10位随机字符
        self.assertTrue(id3.startswith("stream"))
        
        # 测试自定义前缀
        id4 = generate_unique_id("task")
        self.assertEqual(len(id4), 11)  # "task" + 7位随机字符
        self.assertTrue(id4.startswith("task"))
    
    def test_generate_uuid(self):
        """测试UUID生成"""
        id1 = generate_uuid()
        id2 = generate_uuid()
        
        # 验证UUID格式
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        self.assertIsNotNone(re.match(uuid_pattern, id1))
        self.assertIsNotNone(re.match(uuid_pattern, id2))
        self.assertNotEqual(id1, id2)
    
    def test_generate_timestamp_id(self):
        """测试时间戳ID生成"""
        id1 = generate_timestamp_id("ts")
        id2 = generate_timestamp_id("ts")
        
        # 验证时间戳格式
        self.assertTrue(id1.startswith('ts'))
        self.assertTrue(id2.startswith('ts'))
        self.assertNotEqual(id1, id2)
        
        # 验证时间戳部分
        timestamp_part1 = id1[2:]
        timestamp_part2 = id2[2:]
        self.assertTrue(timestamp_part1.isdigit())
        self.assertTrue(timestamp_part2.isdigit())
    
    def test_generate_stream_id(self):
        """测试流ID生成"""
        id1 = generate_unique_id("stream")
        id2 = generate_unique_id("stream")
        
        # 验证流ID格式
        self.assertTrue(id1.startswith('stream'))
        self.assertTrue(id2.startswith('stream'))
        self.assertNotEqual(id1, id2)
        
        # 验证随机部分
        random_part1 = id1[6:]
        random_part2 = id2[6:]
        self.assertEqual(len(random_part1), 7)
        self.assertEqual(len(random_part2), 7)
    
    def test_generate_task_id(self):
        """测试任务ID生成"""
        id1 = generate_unique_id("task")
        id2 = generate_unique_id("task")
        
        # 验证任务ID格式
        self.assertTrue(id1.startswith('task'))
        self.assertTrue(id2.startswith('task'))
        self.assertNotEqual(id1, id2)
        
        # 验证随机部分
        random_part1 = id1[4:]
        random_part2 = id2[4:]
        self.assertEqual(len(random_part1), 7)
        self.assertEqual(len(random_part2), 7)
    
    def test_generate_algorithm_id(self):
        """测试算法ID生成"""
        id1 = generate_unique_id("algo")
        id2 = generate_unique_id("algo")
        
        # 验证算法ID格式
        self.assertTrue(id1.startswith('algo'))
        self.assertTrue(id2.startswith('algo'))
        self.assertNotEqual(id1, id2)
        
        # 验证随机部分
        random_part1 = id1[4:]
        random_part2 = id2[4:]
        self.assertEqual(len(random_part1), 7)
        self.assertEqual(len(random_part2), 7)
    
    def test_id_uniqueness(self):
        """测试ID唯一性"""
        ids = set()
        
        # 生成多个ID并验证唯一性
        for _ in range(100):
            stream_id = generate_unique_id("stream")
            task_id = generate_unique_id("task")
            algorithm_id = generate_unique_id("algo")
            
            self.assertNotIn(stream_id, ids)
            self.assertNotIn(task_id, ids)
            self.assertNotIn(algorithm_id, ids)
            
            ids.add(stream_id)
            ids.add(task_id)
            ids.add(algorithm_id)

if __name__ == "__main__":
    unittest.main() 