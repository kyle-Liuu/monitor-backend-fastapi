"""
事件总线模块
- 实现模块间解耦的消息传递机制
- 支持事件订阅/发布模式
- 使用线程安全队列和回调处理
"""

import threading
import queue
import logging
import time
from typing import Dict, List, Any, Callable, Optional

logger = logging.getLogger(__name__)

class Event:
    """事件类，封装事件数据"""
    
    def __init__(self, event_type: str, sender: str, data: Any = None):
        """初始化事件对象
        
        Args:
            event_type: 事件类型
            sender: 事件发送者标识
            data: 事件携带的数据
        """
        self.event_type = event_type
        self.sender = sender
        self.data = data
        self.timestamp = time.time()
    
    def __str__(self):
        return f"Event({self.event_type}, from={self.sender}, data={self.data})"

class EventBus:
    """事件总线，处理事件的发布和订阅"""
    
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
        self.event_queue = queue.Queue()  # 事件队列
        self.process_thread = None
        self.running = False
        self.lock = threading.RLock()
    
    def start(self):
        """启动事件处理线程"""
        if self.running:
            return
        
        self.running = True
        self.process_thread = threading.Thread(target=self._process_events, daemon=True)
        self.process_thread.start()
        logger.info("事件总线已启动")
    
    def stop(self):
        """停止事件处理线程"""
        if not self.running:
            return
        
        self.running = False
        if self.process_thread:
            self.process_thread.join(timeout=2.0)
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
            return False
        
        try:
            self.event_queue.put(event)
            logger.debug(f"事件已发布: {event}")
            return True
        except Exception as e:
            logger.error(f"发布事件失败: {e}")
            return False
    
    def _process_events(self):
        """事件处理线程函数"""
        logger.info("事件处理线程已启动")
        
        while self.running:
            try:
                # 从队列获取事件，最多等待1秒
                event = self.event_queue.get(timeout=1.0)
                
                # 处理事件
                self._handle_event(event)
                
                # 标记任务完成
                self.event_queue.task_done()
                
            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logger.error(f"处理事件异常: {e}")
        
        logger.info("事件处理线程已退出")
    
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

# 全局事件总线实例
def get_event_bus():
    """获取全局事件总线实例"""
    return EventBus.get_instance() 