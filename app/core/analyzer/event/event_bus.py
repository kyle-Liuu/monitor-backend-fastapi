"""
事件总线模块
- 实现模块间解耦的消息传递机制
- 支持事件发布/订阅模式
- 支持事件优先级和多线程处理
"""

import threading
import queue
import logging
import time
from typing import Dict, List, Any, Callable, Optional

logger = logging.getLogger(__name__)

class Event:
    """事件类，封装事件数据"""
    
    def __init__(self, event_type: str, sender: str, data: Any = None, priority: int = 0):
        """初始化事件对象
        
        Args:
            event_type: 事件类型
            sender: 事件发送者标识
            data: 事件携带的数据
            priority: 事件优先级(0-9)，数字越大优先级越高
        """
        self.event_type = event_type
        self.sender = sender
        self.data = data
        self.timestamp = time.time()
        self.priority = max(0, min(9, priority))  # 限制优先级范围0-9
    
    def __lt__(self, other):
        """比较函数，用于优先级队列"""
        if not isinstance(other, Event):
            return NotImplemented
        return self.priority > other.priority  # 大的优先级值先出队
    
    def __str__(self):
        return f"Event({self.event_type}, from={self.sender}, priority={self.priority}, data={self.data})"

class EventBus:
    """事件总线，处理事件的发布和订阅，支持优先级和多线程处理"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取事件总线单例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = EventBus()
            return cls._instance
    
    def __init__(self):
        """初始化事件总线"""
        self.subscribers = {}  # 类型: {事件类型: [回调函数列表]}
        self.event_queue = queue.PriorityQueue()  # 优先级事件队列
        self.process_threads = []
        self.thread_count = 2  # 默认2个处理线程
        self.running = False
        self.lock = threading.RLock()
        
        # 事件统计
        self.stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "avg_processing_time": 0,
            "max_queue_size": 0
        }
    
    def start(self, thread_count: int = None):
        """启动事件处理线程
        
        Args:
            thread_count: 处理线程数量
        """
        if self.running:
            return
        
        if thread_count is not None:
            self.thread_count = max(1, thread_count)
        
        self.running = True
        
        # 创建并启动处理线程
        for i in range(self.thread_count):
            thread = threading.Thread(
                target=self._process_events,
                name=f"EventProcessor-{i}",
                daemon=True
            )
            thread.start()
            self.process_threads.append(thread)
        
        logger.info(f"事件总线已启动，处理线程数: {self.thread_count}")
    
    def stop(self):
        """停止事件处理线程"""
        if not self.running:
            return
        
        self.running = False
        
        # 等待处理线程结束
        for thread in self.process_threads:
            thread.join(timeout=2.0)
        
        # 清理
        self.process_threads = []
        
        # 清空事件队列
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
                self.event_queue.task_done()
            except:
                pass
        
        logger.info("事件总线已停止")
    
    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> bool:
        """订阅特定类型的事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数，接收Event参数
            
        Returns:
            是否成功订阅
        """
        with self.lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            
            # 避免重复订阅
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)
                logger.debug(f"已订阅事件: {event_type}")
                return True
            return False
    
    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> bool:
        """取消订阅特定类型的事件
        
        Args:
            event_type: 事件类型
            callback: 回调函数
            
        Returns:
            是否成功取消订阅
        """
        with self.lock:
            if event_type in self.subscribers and callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
                logger.debug(f"已取消订阅事件: {event_type}")
                return True
            return False
    
    def publish(self, event: Event) -> bool:
        """发布事件
        
        Args:
            event: 事件对象
            
        Returns:
            是否成功发布
        """
        if not self.running:
            logger.warning(f"事件总线未运行，无法发布事件: {event}")
            self.stats["events_dropped"] += 1
            return False
        
        try:
            # 放入优先级队列
            self.event_queue.put(event)
            self.stats["events_published"] += 1
            
            # 更新最大队列大小统计
            queue_size = self.event_queue.qsize()
            if queue_size > self.stats["max_queue_size"]:
                self.stats["max_queue_size"] = queue_size
            
            logger.debug(f"事件已发布: {event}")
            return True
        except Exception as e:
            logger.error(f"发布事件失败: {e}")
            self.stats["events_dropped"] += 1
            return False
    
    def publish_immediate(self, event: Event) -> bool:
        """立即处理事件（在当前线程）
        
        Args:
            event: 事件对象
            
        Returns:
            是否成功处理
        """
        try:
            # 立即处理事件
            self._handle_event(event)
            self.stats["events_published"] += 1
            self.stats["events_processed"] += 1
            return True
        except Exception as e:
            logger.error(f"立即处理事件失败: {e}")
            self.stats["events_dropped"] += 1
            return False
    
    def _process_events(self):
        """事件处理线程函数"""
        thread_name = threading.current_thread().name
        logger.info(f"事件处理线程已启动: {thread_name}")
        
        while self.running:
            try:
                # 从队列获取事件，最多等待1秒
                event = self.event_queue.get(timeout=1.0)
                
                # 处理事件
                start_time = time.time()
                self._handle_event(event)
                process_time = time.time() - start_time
                
                # 更新统计信息
                self.stats["events_processed"] += 1
                
                # 更新平均处理时间 (移动平均)
                avg = self.stats["avg_processing_time"]
                self.stats["avg_processing_time"] = avg * 0.9 + process_time * 0.1
                
                # 标记任务完成
                self.event_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logger.error(f"处理事件异常: {e}")
        
        logger.info(f"事件处理线程已退出: {thread_name}")
    
    def _handle_event(self, event: Event):
        """处理单个事件"""
        event_type = event.event_type
        
        with self.lock:
            # 获取特定类型的订阅者
            subscribers = self.subscribers.get(event_type, [])
            
            # 获取通配符订阅者 ("*" 表示接收所有事件)
            wildcard_subscribers = self.subscribers.get("*", [])
            
            # 合并订阅者列表
            all_subscribers = subscribers + wildcard_subscribers
        
        # 调用每个订阅者的回调函数
        for callback in all_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"调用事件回调异常: {e}, 事件: {event}")
    
    def get_stats(self) -> Dict:
        """获取事件统计信息"""
        with self.lock:
            stats_copy = self.stats.copy()
            stats_copy["current_queue_size"] = self.event_queue.qsize()
            stats_copy["subscriber_count"] = sum(len(subs) for subs in self.subscribers.values())
            stats_copy["event_types"] = list(self.subscribers.keys())
            return stats_copy
    
    def reset_stats(self):
        """重置统计信息"""
        with self.lock:
            self.stats = {
                "events_published": 0,
                "events_processed": 0,
                "events_dropped": 0,
                "avg_processing_time": 0,
                "max_queue_size": 0
            }

# 全局事件总线实例
def get_event_bus():
    """获取全局事件总线实例"""
    return EventBus.get_instance() 