"""
共享内存管理测试模块
"""

import unittest
import sys
import os
import numpy as np

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.analyzer.memory.shared_memory import SharedMemoryManager

class TestSharedMemory(unittest.TestCase):
    """共享内存测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建新实例，避免影响全局单例
        self.memory_manager = SharedMemoryManager()
        
        # 初始化内存池
        self.num_slots = 10
        self.slot_size = 1024 * 1024  # 1MB
        self.memory_manager.initialize(self.num_slots, self.slot_size)
    
    def tearDown(self):
        """测试后清理"""
        self.memory_manager.shutdown()
    
    def test_initialization(self):
        """测试初始化"""
        status = self.memory_manager.get_status()
        
        self.assertEqual(status["total_slots"], self.num_slots)
        self.assertEqual(status["free_slots"], self.num_slots)
        self.assertEqual(status["used_slots"], 0)
        self.assertEqual(status["total_memory"], self.num_slots * self.slot_size)
    
    def test_allocate_slot(self):
        """测试分配槽位"""
        slot_id = self.memory_manager.allocate_slot("test_stream", 1)
        
        # 应该分配成功
        self.assertGreaterEqual(slot_id, 0)
        
        # 验证状态
        status = self.memory_manager.get_status()
        self.assertEqual(status["free_slots"], self.num_slots - 1)
        self.assertEqual(status["used_slots"], 1)
        
        # 验证槽位详情
        slot_details = status["slot_details"]
        self.assertEqual(len(slot_details), 1)
        self.assertEqual(slot_details[0]["slot_id"], slot_id)
        self.assertEqual(slot_details[0]["stream_id"], "test_stream")
        self.assertEqual(slot_details[0]["frame_id"], 1)
    
    def test_copy_and_retrieve_frame(self):
        """测试复制和读取帧"""
        # 创建测试帧
        test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        # 分配槽位
        slot_id = self.memory_manager.allocate_slot("test_stream", 1)
        
        # 复制到共享内存
        result = self.memory_manager.copy_frame_to_memory(test_frame, slot_id)
        self.assertTrue(result)
        
        # 获取帧信息
        frame_info = self.memory_manager.get_frame_info(slot_id)
        self.assertEqual(frame_info["slot_id"], slot_id)
        self.assertEqual(frame_info["stream_id"], "test_stream")
        self.assertEqual(frame_info["frame_id"], 1)
        self.assertEqual(frame_info["shape"], (480, 640, 3))
        self.assertEqual(frame_info["dtype"], "uint8")
        
        # 读取帧
        retrieved_frame = self.memory_manager.get_frame_from_memory(
            slot_id, (480, 640, 3), np.uint8
        )
        
        # 验证帧数据
        self.assertIsNotNone(retrieved_frame)
        self.assertEqual(retrieved_frame.shape, test_frame.shape)
        self.assertEqual(retrieved_frame.dtype, test_frame.dtype)
        self.assertTrue(np.array_equal(retrieved_frame, test_frame))
    
    def test_reference_counting(self):
        """测试引用计数"""
        # 分配槽位
        slot_id = self.memory_manager.allocate_slot("test_stream", 1)
        
        # 创建和复制测试帧
        test_frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        self.memory_manager.copy_frame_to_memory(test_frame, slot_id)
        
        # 初始引用计数应为1
        frame_info = self.memory_manager.get_frame_info(slot_id)
        self.assertEqual(frame_info["ref_count"], 1)
        
        # 读取增加引用计数
        retrieved_frame = self.memory_manager.get_frame_from_memory(
            slot_id, (480, 640, 3), np.uint8
        )
        
        # 引用计数应增加到2
        frame_info = self.memory_manager.get_frame_info(slot_id)
        self.assertEqual(frame_info["ref_count"], 2)
        
        # 释放一次引用
        self.memory_manager.free_slot(slot_id)
        
        # 引用计数应减为1
        frame_info = self.memory_manager.get_frame_info(slot_id)
        self.assertEqual(frame_info["ref_count"], 1)
        
        # 再释放一次
        self.memory_manager.free_slot(slot_id)
        
        # 槽位应被释放，状态应更新
        status = self.memory_manager.get_status()
        self.assertEqual(status["free_slots"], self.num_slots)
        self.assertEqual(status["used_slots"], 0)
    
    def test_out_of_slots(self):
        """测试槽位耗尽"""
        # 分配所有槽位
        slot_ids = []
        for i in range(self.num_slots):
            slot_id = self.memory_manager.allocate_slot(f"stream_{i}", i)
            self.assertGreaterEqual(slot_id, 0)
            slot_ids.append(slot_id)
        
        # 验证状态
        status = self.memory_manager.get_status()
        self.assertEqual(status["free_slots"], 0)
        self.assertEqual(status["used_slots"], self.num_slots)
        
        # 尝试再分配一个，应失败
        slot_id = self.memory_manager.allocate_slot("extra_stream", 999)
        self.assertEqual(slot_id, -1)
        
        # 释放一个槽位
        self.memory_manager.free_slot(slot_ids[0])
        
        # 应该能分配成功
        slot_id = self.memory_manager.allocate_slot("new_stream", 100)
        self.assertGreaterEqual(slot_id, 0)
    
    def test_frame_too_large(self):
        """测试帧过大的情况"""
        # 分配槽位
        slot_id = self.memory_manager.allocate_slot("test_stream", 1)
        
        # 创建一个大于槽位大小的帧
        large_frame = np.ones((2000, 2000, 3), dtype=np.uint8)  # 超过12MB
        
        # 复制应该失败
        result = self.memory_manager.copy_frame_to_memory(large_frame, slot_id)
        self.assertFalse(result)
    
    def test_garbage_collection(self):
        """测试垃圾回收"""
        # 分配所有槽位
        for i in range(self.num_slots):
            slot_id = self.memory_manager.allocate_slot(f"stream_{i}", i)
            
            # 创建测试帧
            test_frame = np.ones((480, 640, 3), dtype=np.uint8) * i
            self.memory_manager.copy_frame_to_memory(test_frame, slot_id)
            
            # 立即释放引用
            self.memory_manager.free_slot(slot_id)
        
        # 此时所有槽位应该已被释放
        status = self.memory_manager.get_status()
        self.assertEqual(status["free_slots"], self.num_slots)

if __name__ == "__main__":
    unittest.main() 