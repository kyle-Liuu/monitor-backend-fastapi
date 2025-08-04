"""
事件总线测试模块
"""

import unittest
import sys
import os
import time
import threading

# 添加项目路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.analyzer.event.event_bus import Event, EventBus

class TestEventBus(unittest.TestCase):
    """事件总线测试类"""
    
    def setUp(self):
        """测试前设置"""
        # 创建新实例，避免影响全局单例
        self.event_bus = EventBus()
        self.event_bus.start(thread_count=2)
        
        # 用于收集回调中的结果
        self.results = []
        self.event_received = threading.Event()
        
    def tearDown(self):
        """测试后清理"""
        self.event_bus.stop()
        self.results.clear()
        
    def test_event_creation(self):
        """测试事件创建"""
        event = Event("test_event", "test_sender", {"key": "value"}, priority=5)
        
        self.assertEqual(event.event_type, "test_event")
        self.assertEqual(event.sender, "test_sender")
        self.assertEqual(event.data, {"key": "value"})
        self.assertEqual(event.priority, 5)
        
    def test_event_priority(self):
        """测试事件优先级比较"""
        event1 = Event("event1", "sender", priority=3)
        event2 = Event("event2", "sender", priority=7)
        
        # 优先级高的应该先处理
        self.assertTrue(event2 < event1)  # 在优先队列中，较小的先出队，但我们的实现是高优先级先出队
        
    def test_subscribe_unsubscribe(self):
        """测试订阅和取消订阅"""
        def callback(event):
            pass
            
        # 测试订阅
        result = self.event_bus.subscribe("test_event", callback)
        self.assertTrue(result)
        self.assertIn("test_event", self.event_bus.subscribers)
        self.assertIn(callback, self.event_bus.subscribers["test_event"])
        
        # 测试重复订阅
        result = self.event_bus.subscribe("test_event", callback)
        self.assertFalse(result)  # 已存在，应返回False
        
        # 测试取消订阅
        result = self.event_bus.unsubscribe("test_event", callback)
        self.assertTrue(result)
        self.assertEqual(len(self.event_bus.subscribers["test_event"]), 0)
        
        # 测试取消不存在的订阅
        result = self.event_bus.unsubscribe("test_event", callback)
        self.assertFalse(result)
        
    def test_publish_event(self):
        """测试发布事件"""
        def callback(event):
            self.results.append(event.data)
            self.event_received.set()
            
        self.event_bus.subscribe("test_event", callback)
        
        event = Event("test_event", "test_sender", "test_data")
        self.event_bus.publish(event)
        
        # 等待事件处理完成
        self.event_received.wait(timeout=2.0)
        
        self.assertEqual(len(self.results), 1)
        self.assertEqual(self.results[0], "test_data")
        
    def test_wildcard_subscription(self):
        """测试通配符订阅"""
        def callback(event):
            self.results.append(event.event_type)
            self.event_received.set()
            
        # 通配符订阅
        self.event_bus.subscribe("*", callback)
        
        # 发布不同类型的事件
        self.event_bus.publish(Event("event1", "sender"))
        self.event_received.wait(timeout=2.0)
        self.event_received.clear()
        
        self.event_bus.publish(Event("event2", "sender"))
        self.event_received.wait(timeout=2.0)
        
        self.assertEqual(len(self.results), 2)
        self.assertIn("event1", self.results)
        self.assertIn("event2", self.results)
        
    def test_immediate_processing(self):
        """测试立即处理事件"""
        def callback(event):
            self.results.append(event.data)
            
        self.event_bus.subscribe("test_event", callback)
        
        event = Event("test_event", "test_sender", "immediate_data")
        self.event_bus.publish_immediate(event)
        
        # 立即处理不需要等待
        self.assertEqual(len(self.results), 1)
        self.assertEqual(self.results[0], "immediate_data")
        
    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        def callback1(event):
            self.results.append("callback1")
            
        def callback2(event):
            self.results.append("callback2")
            if len(self.results) >= 2:  # 两个回调都执行后
                self.event_received.set()
            
        self.event_bus.subscribe("test_event", callback1)
        self.event_bus.subscribe("test_event", callback2)
        
        self.event_bus.publish(Event("test_event", "sender"))
        
        # 等待事件处理完成
        self.event_received.wait(timeout=2.0)
        
        self.assertEqual(len(self.results), 2)
        self.assertIn("callback1", self.results)
        self.assertIn("callback2", self.results)
        
    def test_event_stats(self):
        """测试事件统计"""
        def callback(event):
            pass
            
        self.event_bus.subscribe("test_event", callback)
        
        for i in range(5):
            self.event_bus.publish(Event("test_event", "sender", f"data{i}"))
            
        # 等待处理完成
        time.sleep(1.0)
        
        stats = self.event_bus.get_stats()
        self.assertEqual(stats["events_published"], 5)
        self.assertEqual(stats["subscriber_count"], 1)
        self.assertIn("test_event", stats["event_types"])

if __name__ == "__main__":
    unittest.main() 