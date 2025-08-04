"""
WebSocket管理器单元测试
测试WebSocket连接管理和告警广播功能
"""

import unittest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from app.core.websocket_manager import UnifiedWebSocketManager, WebSocketType, websocket_manager

class TestWebSocketManager(unittest.TestCase):
    """WebSocket管理器测试类"""
    
    def setUp(self):
        """测试前设置"""
        self.ws_manager = UnifiedWebSocketManager()
        
        # 创建模拟的WebSocket连接
        self.mock_websocket = Mock()
        self.mock_websocket.send_text = AsyncMock()
        self.mock_websocket.close = AsyncMock()
        self.mock_websocket.accept = AsyncMock()
    
    def test_websocket_manager_init(self):
        """测试WebSocket管理器初始化"""
        manager = UnifiedWebSocketManager()
        self.assertIsInstance(manager.connections_by_type, dict)
        self.assertIsInstance(manager.alarm_stream_connections, dict)
        self.assertIsInstance(manager.connection_metadata, dict)
        self.assertIsInstance(manager.connection_stats, dict)
    
    def test_connect_websocket(self):
        """测试连接WebSocket"""
        # 使用异步测试
        async def async_test():
        # 连接WebSocket
            result = await self.ws_manager.connect(self.mock_websocket, WebSocketType.GENERAL.value)
        
            # 验证连接成功
            self.assertTrue(result)
            # 验证连接被添加到正确的类型分组
            self.assertIn(self.mock_websocket, self.ws_manager.connections_by_type[WebSocketType.GENERAL.value])
            
        # 运行异步测试
        asyncio.run(async_test())
    
    def test_disconnect_websocket(self):
        """测试断开WebSocket连接"""
        async def async_test():
        # 先连接
            await self.ws_manager.connect(self.mock_websocket, WebSocketType.GENERAL.value)
        
            # 再断开 (disconnect是同步方法)
        self.ws_manager.disconnect(self.mock_websocket)
        
        # 验证连接被移除
            self.assertNotIn(self.mock_websocket, self.ws_manager.connections_by_type[WebSocketType.GENERAL.value])
            
        asyncio.run(async_test())
    
    def test_subscribe_stream(self):
        """测试订阅流"""
        stream_id = "test_stream_001"
        
        async def async_test():
            # 连接WebSocket（报警类型才能订阅流）
            await self.ws_manager.connect(self.mock_websocket, WebSocketType.ALARMS.value, stream_id)
        
            # 验证流订阅
            self.assertIn(stream_id, self.ws_manager.alarm_stream_connections)
            self.assertIn(self.mock_websocket, self.ws_manager.alarm_stream_connections[stream_id])
        
        asyncio.run(async_test())
    
    def test_unsubscribe_stream(self):
        """测试取消订阅流"""
        stream_id = "test_stream_001"
        
        async def async_test():
        # 连接和订阅
            await self.ws_manager.connect(self.mock_websocket, WebSocketType.ALARMS.value, stream_id)
        
            # 取消订阅（通过断开连接）
            self.ws_manager.disconnect(self.mock_websocket)
        
        # 验证取消订阅
            if stream_id in self.ws_manager.alarm_stream_connections:
                self.assertNotIn(self.mock_websocket, self.ws_manager.alarm_stream_connections[stream_id])
                
        asyncio.run(async_test())
    
    def test_broadcast_to_all(self):
        """测试向所有连接广播"""
        async def async_test():
        # 创建多个模拟连接
        mock_ws1 = Mock()
            mock_ws1.send_text = AsyncMock()
            mock_ws1.accept = AsyncMock()
        mock_ws2 = Mock() 
            mock_ws2.send_text = AsyncMock()
            mock_ws2.accept = AsyncMock()
        
        # 连接WebSocket
            await self.ws_manager.connect(mock_ws1, WebSocketType.GENERAL.value)
            await self.ws_manager.connect(mock_ws2, WebSocketType.STATUS.value)
        
        # 测试消息
        message = {"type": "test", "data": "hello"}
            message_str = json.dumps(message)
            
            # 广播消息
            sent_count = await self.ws_manager.broadcast_to_all(message_str)
            
            # 验证所有连接都收到消息
            self.assertEqual(sent_count, 2)
            mock_ws1.send_text.assert_called_once_with(message_str)
            mock_ws2.send_text.assert_called_once_with(message_str)
            
        asyncio.run(async_test())
    
    def test_broadcast_to_stream_subscribers(self):
        """测试向流订阅者广播"""
        async def async_test():
        stream_id = "test_stream_001"
        
        # 创建多个模拟连接
        mock_ws1 = Mock()
            mock_ws1.send_text = AsyncMock()
            mock_ws1.accept = AsyncMock()
        mock_ws2 = Mock()
            mock_ws2.send_text = AsyncMock()
            mock_ws2.accept = AsyncMock()
        
            # 连接并订阅流
            await self.ws_manager.connect(mock_ws1, WebSocketType.ALARMS.value, stream_id)
            await self.ws_manager.connect(mock_ws2, WebSocketType.GENERAL.value)  # 不订阅流
        
        # 测试消息
            message = {"type": "stream_update", "stream_id": stream_id, "data": "stream data"}
            message_str = json.dumps(message)
            
            # 广播到流订阅者
            sent_count = await self.ws_manager.broadcast_to_stream(message_str, stream_id)
            
            # 验证只有订阅流的连接收到消息
            self.assertEqual(sent_count, 1)
            mock_ws1.send_text.assert_called_once_with(message_str)
            mock_ws2.send_text.assert_not_called()
            
        asyncio.run(async_test())
    
    def test_send_personal_message(self):
        """测试发送个人消息"""
        async def async_test():
            # 连接WebSocket
            await self.ws_manager.connect(self.mock_websocket, WebSocketType.GENERAL.value)
            
            # 测试消息
        message = {"type": "personal", "data": "hello"}
            message_str = json.dumps(message)
            
            # 发送个人消息 (注意参数顺序：message, websocket)
            success = await self.ws_manager.send_personal_message(message_str, self.mock_websocket)
            
            # 验证消息发送成功
            self.assertTrue(success)
            self.mock_websocket.send_text.assert_called_once_with(message_str)
            
        asyncio.run(async_test())
    
    def test_broadcast_alarm_new_feature(self):
        """测试新增的告警广播功能"""
        async def async_test():
            # 创建多个模拟连接
            mock_ws1 = Mock()
            mock_ws1.send_text = AsyncMock()
            mock_ws1.accept = AsyncMock()
            mock_ws2 = Mock()
            mock_ws2.send_text = AsyncMock() 
            mock_ws2.accept = AsyncMock()
            
            # 连接不同类型的WebSocket
            await self.ws_manager.connect(mock_ws1, WebSocketType.ALARMS.value)
            await self.ws_manager.connect(mock_ws2, WebSocketType.STATUS.value)
            
            # 测试告警消息
        alarm_data = {
            "alarm_id": "alarm_test_001",
                "type": "person_detection",
                "confidence": 0.95,
                "timestamp": datetime.now().isoformat()
        }
        
            # 广播告警到报警连接
            sent_count = await self.ws_manager.broadcast_alarm(alarm_data)
            
            # 验证只有报警连接收到消息
            self.assertEqual(sent_count, 1)
            mock_ws1.send_text.assert_called_once()
            mock_ws2.send_text.assert_not_called()
            
        asyncio.run(async_test())
    
    def test_websocket_connection_error_handling(self):
        """测试WebSocket连接错误处理"""
        async def async_test():
            # 创建会抛出异常的模拟WebSocket
        mock_ws_error = Mock()
            mock_ws_error.send_text = AsyncMock(side_effect=Exception("Connection error"))
            mock_ws_error.accept = AsyncMock()
            
            # 连接WebSocket
            await self.ws_manager.connect(mock_ws_error, WebSocketType.GENERAL.value)
        
            # 尝试发送消息（应该处理异常）
            message = {"type": "test", "data": "test"}
            message_str = json.dumps(message)
            success = await self.ws_manager.send_personal_message(message_str, mock_ws_error)
            
            # 验证错误处理
            self.assertFalse(success)
            
        asyncio.run(async_test())
    
    def test_get_connection_stats(self):
        """测试获取连接统计"""
        async def async_test():
            # 创建多个连接
        mock_ws1 = Mock()
            mock_ws1.accept = AsyncMock()
        mock_ws2 = Mock()
            mock_ws2.accept = AsyncMock()
            
            # 连接不同类型
            await self.ws_manager.connect(mock_ws1, WebSocketType.ALARMS.value, "stream_001")
            await self.ws_manager.connect(mock_ws2, WebSocketType.STATUS.value)
            
            # 获取统计信息
            stats = self.ws_manager.get_connection_stats()
        
            # 验证统计信息
            self.assertEqual(stats["total_connections"], 2)
            self.assertEqual(stats["connections_by_type"][WebSocketType.ALARMS.value], 1)
            self.assertEqual(stats["connections_by_type"][WebSocketType.STATUS.value], 1)
            
        asyncio.run(async_test())

class TestWebSocketManagerIntegration(unittest.TestCase):
    """WebSocket管理器集成测试"""
    
    def setUp(self):
        """测试前设置"""
        self.ws_manager = UnifiedWebSocketManager()
    
    def test_full_subscription_and_alarm_flow(self):
        """测试完整的订阅和告警流程"""
        async def async_test():
            stream_id = "test_stream_001"
            
            # 创建模拟连接
            mock_ws = Mock()
            mock_ws.send_text = AsyncMock()
            mock_ws.accept = AsyncMock()
        
            # 连接并订阅流
            await self.ws_manager.connect(mock_ws, WebSocketType.ALARMS.value, stream_id)
            
            # 模拟告警数据
            alarm_data = {
                "alarm_id": "alarm_test_001",
                "stream_id": stream_id,
                "type": "person_detection",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
                "timestamp": datetime.now().isoformat()
            }
            
            # 发送流特定告警
            message_str = json.dumps({
                "type": "alarm",
                "data": alarm_data
            })
            sent_count = await self.ws_manager.broadcast_to_stream(message_str, stream_id)
            
            # 验证告警被发送
            self.assertEqual(sent_count, 1)
            mock_ws.send_text.assert_called_once_with(message_str)
            
        asyncio.run(async_test())
    
    def test_cleanup_on_disconnect(self):
        """测试断开连接时的清理"""
        async def async_test():
            stream_id = "test_stream_001"
        
            # 创建模拟连接
        mock_ws = Mock()
            mock_ws.accept = AsyncMock()
            
            # 连接并订阅流
            await self.ws_manager.connect(mock_ws, WebSocketType.ALARMS.value, stream_id)
        
            # 验证连接已建立
            self.assertIn(mock_ws, self.ws_manager.connections_by_type[WebSocketType.ALARMS.value])
            self.assertIn(stream_id, self.ws_manager.alarm_stream_connections)
        
            # 断开连接 (disconnect是同步方法)
        self.ws_manager.disconnect(mock_ws)
        
            # 验证清理完成
            self.assertNotIn(mock_ws, self.ws_manager.connections_by_type[WebSocketType.ALARMS.value])
            # 流连接应该被清理（如果没有其他连接）
            if stream_id in self.ws_manager.alarm_stream_connections:
                self.assertEqual(len(self.ws_manager.alarm_stream_connections[stream_id]), 0)
                
        asyncio.run(async_test())

if __name__ == '__main__':
    unittest.main() 