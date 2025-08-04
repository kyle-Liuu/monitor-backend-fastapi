"""
进程间通信与状态共享模块
- 共享队列/内存：帧队列、结果队列、告警队列，多进程安全复用
- 状态共享：Manager字典+文件快照
- put/get_frame、put/get_result、put/get_alarm等接口注释清晰
- 只保留分析器主线相关内容
"""

import os
import sys
import time
import uuid
import logging
import numpy as np
import queue
import threading
import multiprocessing as mp
import json
import tempfile
from multiprocessing import shared_memory
from multiprocessing.queues import Empty as MPQueueEmpty  # 添加多进程队列专用的Empty异常

logger = logging.getLogger(__name__)

# 生成全局唯一的资源名称前缀，避免冲突
RESOURCE_PREFIX = f"ipc_{time.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

# 进程本地引用计数字典
_local_ref_counts = {}
_local_ref_lock = threading.RLock()

# 状态文件的基础目录
STATUS_BASE_DIR = os.path.join(tempfile.gettempdir(), "video_analyzer_status")
os.makedirs(STATUS_BASE_DIR, exist_ok=True)

def get_queue_name(manager_id, stream_id=None, algo_id=None, type_prefix=""):
    """生成队列名称"""
    if stream_id and algo_id:
        return f"{type_prefix}_{manager_id}_{stream_id}_{algo_id}"
    elif stream_id:
        return f"{type_prefix}_{manager_id}_{stream_id}"
    else:
        return f"{type_prefix}_{manager_id}"

class FrameReference:
    """帧引用类，用于在进程间共享帧数据的引用"""
    def __init__(self, shm_name, shape, dtype, frame_id, timestamp):
        self.shm_name = shm_name
        self.shape = shape
        self.dtype = dtype
        self.frame_id = frame_id
        self.timestamp = timestamp
        
        # 初始化进程本地引用计数
        global _local_ref_counts, _local_ref_lock
        with _local_ref_lock:
            if self.frame_id not in _local_ref_counts:
                _local_ref_counts[self.frame_id] = 1
            else:
                _local_ref_counts[self.frame_id] += 1

    def get_array(self):
        """获取共享内存中的数组"""
        try:
            shm = shared_memory.SharedMemory(name=self.shm_name)
            array = np.ndarray(self.shape, dtype=self.dtype, buffer=shm.buf)
            return array, shm
        except Exception as e:
            logger.error(f"获取共享内存数组失败: {e}")
            return None, None

    def increment_ref(self):
        """增加引用计数"""
        global _local_ref_counts, _local_ref_lock
        with _local_ref_lock:
            if self.frame_id not in _local_ref_counts:
                _local_ref_counts[self.frame_id] = 1
            else:
                _local_ref_counts[self.frame_id] += 1
            return _local_ref_counts[self.frame_id]

    def decrement_ref(self):
        """减少引用计数，返回当前计数值"""
        global _local_ref_counts, _local_ref_lock
        with _local_ref_lock:
            if self.frame_id in _local_ref_counts:
                _local_ref_counts[self.frame_id] = max(0, _local_ref_counts[self.frame_id] - 1)
                return _local_ref_counts[self.frame_id]
            return 0


class SharedMemoryManager:
    """共享内存管理器"""
    def __init__(self):
        self.shared_blocks = {}
        self._lock = threading.RLock()  # 使用线程锁而非进程锁

    def create_shared_frame(self, frame):
        """创建共享内存帧"""
        frame_id = str(uuid.uuid4())
        timestamp = time.time()
        
        try:
            # 创建共享内存块
            shm = shared_memory.SharedMemory(create=True, size=frame.nbytes)
            
            # 将帧数据复制到共享内存
            shared_array = np.ndarray(frame.shape, dtype=frame.dtype, buffer=shm.buf)
            shared_array[:] = frame[:]
            
            # 创建帧引用对象
            frame_ref = FrameReference(
                shm_name=shm.name,
                shape=frame.shape,
                dtype=frame.dtype,
                frame_id=frame_id,
                timestamp=timestamp
            )
            
            # 记录共享内存块
            with self._lock:
                self.shared_blocks[frame_id] = {
                    'shm': shm,
                    'ref': frame_ref
                }
            
            return frame_ref
            
        except Exception as e:
            logger.error(f"创建共享内存帧失败: {e}")
            return None

    def get_frame(self, frame_ref):
        """根据帧引用获取帧数据"""
        array, shm = frame_ref.get_array()
        if array is not None:
            # 返回数组的副本，防止修改原数据
            # 极致零拷贝，将 SharedMemoryManager.get_frame 的 return array.copy() 改为 return array
            return array.copy()
        return None

    def release_frame(self, frame_ref):
        """释放帧引用，当引用计数为0时释放共享内存"""
        if not frame_ref:
            return
            
        ref_count = frame_ref.decrement_ref()
        
        if ref_count <= 0:
            # 最后一个引用被释放，清理共享内存
            with self._lock:
                if frame_ref.frame_id in self.shared_blocks:
                    try:
                        block = self.shared_blocks[frame_ref.frame_id]
                        block['shm'].close()
                        block['shm'].unlink()
                        del self.shared_blocks[frame_ref.frame_id]
                    except Exception as e:
                        logger.error(f"释放共享内存块失败: {e}")


class IPCManager:
    """进程间通信管理器"""
    
    def __init__(self, max_queue_size=10, manager_id=None):
        """
        初始化进程间通信管理器
        
        参数:
            max_queue_size: 队列最大长度
            manager_id: 管理器ID，用于标识同一组管理器共享的资源
        """
        self.manager_id = manager_id or RESOURCE_PREFIX
        self.max_queue_size = max_queue_size
        
        # 使用普通队列替代Manager队列
        self.frame_queues = {}  # 用于存放各个流的帧队列
        self.result_queues = {}  # 用于存放各个算法的结果队列
        
        # 告警队列
        self.alarm_queue = mp.Queue(maxsize=100)  
        
        # 使用普通字典替代共享字典
        self.stream_status = {}
        self.algo_status = {}
        self.output_status = {}
        
        # 共享内存管理
        self.memory_manager = SharedMemoryManager()
        
        # 状态文件基础路径
        self.status_dir = os.path.join(STATUS_BASE_DIR, self.manager_id)
        os.makedirs(self.status_dir, exist_ok=True)
        
        logger.info(f"IPC管理器初始化完成，ID: {self.manager_id}")
        
    def _get_status_file_path(self, status_type, key):
        """获取状态文件路径"""
        return os.path.join(self.status_dir, f"{status_type}_{key}.json")
    
    def set_shared_status(self, status_type, key, status_data):
        """设置共享状态"""
        try:
            file_path = self._get_status_file_path(status_type, key)
            with open(file_path, 'w') as f:
                json.dump(status_data, f)
            
            # 同时更新本地状态字典
            if status_type == 'algo':
                self.algo_status[key] = status_data
            elif status_type == 'stream':
                self.stream_status[key] = status_data
            elif status_type == 'output':
                self.output_status[key] = status_data
                
            return True
        except Exception as e:
            logger.error(f"设置共享状态失败: {status_type}, {key}, 错误: {e}")
            return False
    
    def get_shared_status(self, status_type, key):
        """获取共享状态"""
        try:
            file_path = self._get_status_file_path(status_type, key)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    status_data = json.load(f)
                
                # 更新本地状态字典
                if status_type == 'algo':
                    self.algo_status[key] = status_data
                elif status_type == 'stream':
                    self.stream_status[key] = status_data
                elif status_type == 'output':
                    self.output_status[key] = status_data
                
                return status_data
            else:
                return None
        except Exception as e:
            logger.error(f"获取共享状态失败: {status_type}, {key}, 错误: {e}")
            return None
    
    def get_all_shared_status(self, status_type):
        """获取所有共享状态"""
        try:
            result = {}
            status_prefix = f"{status_type}_"
            
            for filename in os.listdir(self.status_dir):
                if filename.startswith(status_prefix) and filename.endswith('.json'):
                    key = filename[len(status_prefix):-5]  # 去掉前缀和.json后缀
                    status_data = self.get_shared_status(status_type, key)
                    if status_data:
                        result[key] = status_data
            
            # 更新本地状态字典
            if status_type == 'algo':
                self.algo_status.update(result)
            elif status_type == 'stream':
                self.stream_status.update(result)
            elif status_type == 'output':
                self.output_status.update(result)
                
            return result
        except Exception as e:
            logger.error(f"获取所有共享状态失败: {status_type}, 错误: {e}")
            return {}
    
    def create_stream_queue(self, stream_id):
        """创建视频流队列"""
        if stream_id not in self.frame_queues:
            self.frame_queues[stream_id] = mp.Queue(maxsize=self.max_queue_size)
            status_data = {
                'status': 'initialized',
                'last_frame_time': 0,
                'frame_count': 0,
                'errors': 0
            }
            self.stream_status[stream_id] = status_data
            # 写入共享状态
            self.set_shared_status('stream', stream_id, status_data)
        return self.frame_queues[stream_id]
    
    def create_result_queue(self, stream_id, algo_id):
        """创建算法结果队列"""
        key = f"{stream_id}_{algo_id}"
        if key not in self.result_queues:
            self.result_queues[key] = mp.Queue(maxsize=self.max_queue_size)
            status_data = {
                'status': 'initialized',
                'last_process_time': 0,
                'processed_count': 0,
                'errors': 0
            }
            self.algo_status[key] = status_data
            # 写入共享状态
            self.set_shared_status('algo', key, status_data)
        return self.result_queues[key]
    
    def put_frame(self, stream_id, frame):
        """将帧放入队列"""
        if stream_id not in self.frame_queues:
            self.create_stream_queue(stream_id)
        
        queue = self.frame_queues[stream_id]
        
        # 如果队列满，丢弃最旧的帧
        if queue.full():
            try:
                old_frame_ref = queue.get_nowait()
                self.memory_manager.release_frame(old_frame_ref)
            except MPQueueEmpty:
                pass
        
        # 创建共享内存帧
        frame_ref = self.memory_manager.create_shared_frame(frame)
        if not frame_ref:
            return False
            
        # 更新流状态
        # 先获取最新的共享状态
        status = self.get_shared_status('stream', stream_id) or self.stream_status.get(stream_id, {})
        status['last_frame_time'] = time.time()
        status['frame_count'] = status.get('frame_count', 0) + 1
        self.stream_status[stream_id] = status
        # 更新共享状态
        self.set_shared_status('stream', stream_id, status)
        
        # 放入队列
        try:
            queue.put(frame_ref)
            return True
        except Exception as e:
            logger.error(f"放入帧失败: {e}")
            return False
    
    def get_frame(self, stream_id, timeout=1.0):
        """从队列获取帧引用"""
        if stream_id not in self.frame_queues:
            self.create_stream_queue(stream_id)
            return None
            
        queue = self.frame_queues[stream_id]
        
        try:
            frame_ref = queue.get(timeout=timeout)
            # 增加引用计数
            frame_ref.increment_ref()
            return frame_ref
        except (MPQueueEmpty, Exception) as e:
            if not isinstance(e, MPQueueEmpty):
                logger.error(f"获取帧失败: {e}")
            return None
    
    def put_result(self, stream_id, algo_id, frame_ref, result_data):
        """将算法结果放入队列"""
        key = f"{stream_id}_{algo_id}"
        if key not in self.result_queues:
            self.create_result_queue(stream_id, algo_id)
            
        queue = self.result_queues[key]
        
        # 如果队列满，丢弃最旧的结果
        if queue.full():
            try:
                old_result = queue.get_nowait()
                if 'frame_ref' in old_result:
                    self.memory_manager.release_frame(old_result['frame_ref'])
            except MPQueueEmpty:
                pass
        
        try:
            # 增加帧引用计数
            frame_ref.increment_ref()
            
            # 创建结果对象
            result = {
                'frame_ref': frame_ref,
                'result_data': result_data,
                'timestamp': time.time()
            }
            
            # 更新算法状态
            # 先获取最新的共享状态
            status = self.get_shared_status('algo', key) or self.algo_status.get(key, {})
            status['last_process_time'] = time.time()
            status['processed_count'] = status.get('processed_count', 0) + 1
            self.algo_status[key] = status
            # 更新共享状态
            self.set_shared_status('algo', key, status)
            
            # 放入队列
            queue.put(result)
            return True
        except Exception as e:
            logger.error(f"放入结果失败: {e}")
            return False
    
    def get_result(self, stream_id, algo_id, timeout=1.0):
        """获取算法结果"""
        key = f"{stream_id}_{algo_id}"
        if key not in self.result_queues:
            self.create_result_queue(stream_id, algo_id)
            return None
            
        queue = self.result_queues[key]
        
        try:
            return queue.get(timeout=timeout)
        except (MPQueueEmpty, Exception) as e:
            if not isinstance(e, MPQueueEmpty):
                logger.error(f"获取结果失败: {e}")
            return None
    
    def put_alarm(self, alarm_data):
        # 支持双份图片推送
        self.alarm_queue.put(alarm_data)
        logger.info(f"推送告警数据: {alarm_data['frame_id']} 包含原图和画框图")
    
    def get_alarm(self, timeout=1.0):
        """获取告警信息"""
        try:
            return self.alarm_queue.get(timeout=timeout)
        except (MPQueueEmpty, Exception) as e:
            if not isinstance(e, MPQueueEmpty):
                logger.error(f"获取告警失败: {e}")
            return None
    
    def cleanup(self):
        """清理资源"""
        # 清理所有队列
        for stream_id in list(self.frame_queues.keys()):
            queue = self.frame_queues[stream_id]
            while True:
                try:
                    frame_ref = queue.get_nowait()
                    self.memory_manager.release_frame(frame_ref)
                except:
                    break
        
        for key in list(self.result_queues.keys()):
            queue = self.result_queues[key]
            while True:
                try:
                    result = queue.get_nowait()
                    if 'frame_ref' in result:
                        self.memory_manager.release_frame(result['frame_ref'])
                except MPQueueEmpty:
                    break
        
        # 清理状态文件
        try:
            if os.path.exists(self.status_dir):
                for filename in os.listdir(self.status_dir):
                    file_path = os.path.join(self.status_dir, filename)
                    try:
                        os.remove(file_path)
                    except:
                        pass
                try:
                    os.rmdir(self.status_dir)
                except:
                    pass
        except Exception as e:
            logger.error(f"清理状态文件失败: {e}")
    
    # 重写get_status方法，确保获取最新的共享状态
    def get_algo_status(self):
        """获取所有算法状态"""
        return self.get_all_shared_status('algo')
    
    def get_stream_status(self):
        """获取所有流状态"""
        return self.get_all_shared_status('stream')
    
    def get_output_status(self):
        """获取所有输出状态"""
        return self.get_all_shared_status('output') 