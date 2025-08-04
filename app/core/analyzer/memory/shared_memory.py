"""
共享内存管理模块
- 优化视频帧的共享内存机制
- 实现基于引用计数的内存回收机制
- 降低帧复制次数
"""

import threading
import numpy as np
import mmap
import logging
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger(__name__)

class MemorySlot:
    """内存槽"""
    
    def __init__(self, slot_id: int, size: int, memory: mmap.mmap):
        """初始化内存槽"""
        self.slot_id = slot_id
        self.size = size
        self.memory = memory
        self.in_use = False
        self.ref_count = 0
        self.stream_id = None
        self.frame_id = None
        self.timestamp = 0
        self.shape = None
        self.dtype = None
        
    def increment_ref(self):
        """增加引用计数"""
        self.ref_count += 1
        
    def decrement_ref(self):
        """减少引用计数"""
        if self.ref_count > 0:
            self.ref_count -= 1
        
    def can_free(self) -> bool:
        """是否可以释放"""
        return self.ref_count == 0

class SharedMemoryManager:
    """共享内存管理器"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = SharedMemoryManager()
            return cls._instance
    
    def __init__(self):
        """初始化共享内存管理器"""
        self.slots = {}  # {slot_id: MemorySlot}
        self.free_slots = []  # 空闲槽ID列表
        self.lock = threading.RLock()
        self.total_slots = 0
        self.total_memory = 0
        
    def initialize(self, num_slots: int, slot_size: int):
        """初始化内存池"""
        with self.lock:
            self.total_slots = num_slots
            self.total_memory = num_slots * slot_size
            
            for i in range(num_slots):
                try:
                    # 创建内存映射
                    memory = mmap.mmap(-1, slot_size)
                    
                    # 创建槽
                    self.slots[i] = MemorySlot(i, slot_size, memory)
                    self.free_slots.append(i)
                    
                except Exception as e:
                    logger.error(f"创建内存槽异常: {e}")
                    
            logger.info(f"初始化内存池: {num_slots}槽, 每槽{slot_size}字节")
    
    def allocate_slot(self, stream_id: str, frame_id: int = 0) -> int:
        """分配内存槽"""
        with self.lock:
            if not self.free_slots:
                # 尝试回收未使用的槽
                self._garbage_collect()
                
            if not self.free_slots:
                logger.warning("无可用内存槽")
                return -1
                
            # 分配槽
            slot_id = self.free_slots.pop(0)
            slot = self.slots[slot_id]
            
            # 标记为使用中
            slot.in_use = True
            slot.ref_count = 1
            slot.stream_id = stream_id
            slot.frame_id = frame_id
            slot.timestamp = 0  # 将在复制时设置
            
            return slot_id
    
    def _garbage_collect(self):
        """垃圾回收 - 释放未使用的槽"""
        for slot_id, slot in self.slots.items():
            if slot.in_use and slot.can_free():
                # 重置槽
                slot.in_use = False
                slot.ref_count = 0
                slot.stream_id = None
                slot.frame_id = None
                slot.timestamp = 0
                slot.shape = None
                slot.dtype = None
                
                # 添加到空闲列表
                self.free_slots.append(slot_id)
                
                logger.debug(f"垃圾回收释放槽: {slot_id}")
    
    def copy_frame_to_memory(self, frame: np.ndarray, slot_id: int) -> bool:
        """将帧复制到共享内存"""
        if slot_id < 0 or slot_id >= self.total_slots:
            logger.error(f"无效的槽ID: {slot_id}")
            return False
            
        with self.lock:
            slot = self.slots.get(slot_id)
            if not slot or not slot.in_use:
                logger.error(f"槽未分配: {slot_id}")
                return False
                
            try:
                # 检查帧大小
                frame_size = frame.nbytes
                if frame_size > slot.size:
                    logger.error(f"帧太大，无法复制: {frame_size} > {slot.size}")
                    return False
                
                # 保存帧信息
                slot.shape = frame.shape
                slot.dtype = str(frame.dtype)
                slot.timestamp = 0  # TODO: 设置实际时间戳
                
                # 复制帧数据
                slot.memory.seek(0)
                slot.memory.write(frame.tobytes())
                
                return True
                
            except Exception as e:
                logger.error(f"复制帧异常: {e}")
                return False
    
    def get_frame_from_memory(self, slot_id: int, shape: tuple, dtype: np.dtype) -> Optional[np.ndarray]:
        """从共享内存获取帧"""
        if slot_id < 0 or slot_id >= self.total_slots:
            logger.error(f"无效的槽ID: {slot_id}")
            return None
            
        with self.lock:
            slot = self.slots.get(slot_id)
            if not slot or not slot.in_use:
                logger.error(f"槽未分配: {slot_id}")
                return None
                
            try:
                # 增加引用计数
                slot.increment_ref()
                
                # 从内存读取
                slot.memory.seek(0)
                buffer = slot.memory.read(np.prod(shape) * np.dtype(dtype).itemsize)
                
                # 转换为数组
                frame = np.frombuffer(buffer, dtype=dtype).reshape(shape)
                
                return frame.copy()  # 返回副本，避免内存共享问题
                
            except Exception as e:
                logger.error(f"获取帧异常: {e}")
                return None
    
    def get_frame_info(self, slot_id: int) -> Optional[Dict]:
        """获取帧信息"""
        with self.lock:
            slot = self.slots.get(slot_id)
            if not slot or not slot.in_use:
                return None
                
            return {
                "slot_id": slot_id,
                "stream_id": slot.stream_id,
                "frame_id": slot.frame_id,
                "timestamp": slot.timestamp,
                "shape": slot.shape,
                "dtype": slot.dtype,
                "ref_count": slot.ref_count
            }
    
    def free_slot(self, slot_id: int) -> bool:
        """释放内存槽（减少引用计数）"""
        with self.lock:
            slot = self.slots.get(slot_id)
            if not slot or not slot.in_use:
                return False
                
            # 减少引用计数
            slot.decrement_ref()
            
            # 如果引用计数为0，立即回收
            if slot.can_free():
                slot.in_use = False
                slot.stream_id = None
                slot.frame_id = None
                slot.timestamp = 0
                slot.shape = None
                slot.dtype = None
                
                self.free_slots.append(slot_id)
                
            return True
    
    def get_status(self) -> Dict:
        """获取状态信息"""
        with self.lock:
            total = self.total_slots
            used = total - len(self.free_slots)
            
            return {
                "total_slots": total,
                "used_slots": used,
                "free_slots": len(self.free_slots),
                "usage_percent": (used / total * 100) if total > 0 else 0,
                "total_memory": self.total_memory,
                "slot_details": [
                    {
                        "slot_id": i,
                        "in_use": slot.in_use,
                        "ref_count": slot.ref_count,
                        "stream_id": slot.stream_id,
                        "frame_id": slot.frame_id
                    }
                    for i, slot in self.slots.items() if slot.in_use
                ]
            }
    
    def shutdown(self):
        """关闭管理器并释放资源"""
        with self.lock:
            for slot in self.slots.values():
                try:
                    if slot.memory:
                        slot.memory.close()
                except:
                    pass
            
            self.slots.clear()
            self.free_slots.clear()
            self.total_slots = 0
            self.total_memory = 0
            
            logger.info("共享内存管理器已关闭")

# 全局共享内存管理器实例
shared_memory_manager = SharedMemoryManager.get_instance() 