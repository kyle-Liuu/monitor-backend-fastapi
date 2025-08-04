"""
统一的WebSocket连接管理器
整合报警WebSocket和状态WebSocket的连接管理
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Set, Optional, Any
import json
import logging
import asyncio
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class WebSocketType(Enum):
    """WebSocket连接类型"""
    ALARMS = "alarms"        # 报警WebSocket
    STATUS = "status"        # 状态WebSocket
    GENERAL = "general"      # 通用WebSocket

class UnifiedWebSocketManager:
    """统一的WebSocket连接管理器"""
    
    def __init__(self):
        # 按类型分组的连接
        self.connections_by_type: Dict[str, List[WebSocket]] = {
            WebSocketType.ALARMS.value: [],
            WebSocketType.STATUS.value: [],
            WebSocketType.GENERAL.value: []
        }
        
        # 按流ID分组的报警连接（用于流特定广播）
        self.alarm_stream_connections: Dict[str, List[WebSocket]] = {}
        
        # 连接元数据
        self.connection_metadata: Dict[WebSocket, Dict] = {}
        
        # 统计信息
        self.connection_stats = {
            "total_connections": 0,
            "connections_by_type": {t.value: 0 for t in WebSocketType},
            "stream_subscriptions": 0
        }
    
    async def connect(self, websocket: WebSocket, ws_type: str, 
                     stream_id: str = None, client_info: Dict = None):
        """建立WebSocket连接"""
        try:
            await websocket.accept()
            
            # 添加到类型分组
            if ws_type not in self.connections_by_type:
                self.connections_by_type[ws_type] = []
            self.connections_by_type[ws_type].append(websocket)
            
            # 如果是报警连接且指定了流ID，添加到流分组
            if ws_type == WebSocketType.ALARMS.value and stream_id:
                if stream_id not in self.alarm_stream_connections:
                    self.alarm_stream_connections[stream_id] = []
                self.alarm_stream_connections[stream_id].append(websocket)
                self.connection_stats["stream_subscriptions"] += 1
            
            # 保存连接元数据
            self.connection_metadata[websocket] = {
                "type": ws_type,
                "stream_id": stream_id,
                "client_info": client_info or {},
                "connected_time": datetime.now(),
                "last_activity": datetime.now()
            }
            
            # 更新统计
            self.connection_stats["total_connections"] += 1
            self.connection_stats["connections_by_type"][ws_type] += 1
            
            logger.info(f"WebSocket连接建立 - 类型: {ws_type}, 流ID: {stream_id}, "
                       f"总连接数: {self.connection_stats['total_connections']}")
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket连接建立失败: {e}")
            return False
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        try:
            metadata = self.connection_metadata.get(websocket, {})
            ws_type = metadata.get("type", "unknown")
            stream_id = metadata.get("stream_id")
            
            # 从类型分组中移除
            for conn_type, connections in self.connections_by_type.items():
                if websocket in connections:
                    connections.remove(websocket)
                    self.connection_stats["connections_by_type"][conn_type] -= 1
            
            # 从流分组中移除
            if stream_id and stream_id in self.alarm_stream_connections:
                if websocket in self.alarm_stream_connections[stream_id]:
                    self.alarm_stream_connections[stream_id].remove(websocket)
                    self.connection_stats["stream_subscriptions"] -= 1
                    
                    # 如果流没有连接了，删除空列表
                    if not self.alarm_stream_connections[stream_id]:
                        del self.alarm_stream_connections[stream_id]
            
            # 删除元数据
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            # 更新统计
            self.connection_stats["total_connections"] -= 1
            
            logger.info(f"WebSocket连接断开 - 类型: {ws_type}, 流ID: {stream_id}, "
                       f"总连接数: {self.connection_stats['total_connections']}")
            
        except Exception as e:
            logger.error(f"WebSocket连接断开处理失败: {e}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
            
            # 更新活动时间
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["last_activity"] = datetime.now()
                
            return True
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            self.disconnect(websocket)
            return False
    
    async def broadcast_to_type(self, message: str, ws_type: str):
        """向特定类型的所有连接广播消息"""
        if ws_type not in self.connections_by_type:
            logger.warning(f"未知的WebSocket类型: {ws_type}")
            return 0
        
        connections = self.connections_by_type[ws_type].copy()
        disconnected = []
        sent_count = 0
        
        for connection in connections:
            try:
                await connection.send_text(message)
                
                # 更新活动时间
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["last_activity"] = datetime.now()
                
                sent_count += 1
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
        
        logger.debug(f"广播到类型 {ws_type}: 发送成功 {sent_count}/{len(connections)} 个连接")
        return sent_count
    
    async def broadcast_to_stream(self, message: str, stream_id: str):
        """向特定流的订阅者广播消息"""
        if stream_id not in self.alarm_stream_connections:
            logger.debug(f"流 {stream_id} 没有订阅者")
            return 0
        
        connections = self.alarm_stream_connections[stream_id].copy()
        disconnected = []
        sent_count = 0
        
        for connection in connections:
            try:
                await connection.send_text(message)
                
                # 更新活动时间
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]["last_activity"] = datetime.now()
                
                sent_count += 1
            except Exception as e:
                logger.error(f"向流广播消息失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
        
        logger.debug(f"广播到流 {stream_id}: 发送成功 {sent_count}/{len(connections)} 个连接")
        return sent_count
    
    async def broadcast_to_all(self, message: str):
        """向所有连接广播消息"""
        total_sent = 0
        for ws_type in self.connections_by_type:
            sent = await self.broadcast_to_type(message, ws_type)
            total_sent += sent
        
        logger.debug(f"全局广播: 发送成功 {total_sent} 个连接")
        return total_sent
    
    async def broadcast_alarm(self, alarm_data: Dict[str, Any]):
        """
        广播告警通知
        
        Args:
            alarm_data: 告警数据
                {
                    "type": "alarm",
                    "alarm_id": "alarm_xxx",
                    "task_id": "task_xxx", 
                    "stream_id": "stream_xxx",
                    "timestamp": "2024-12-19T14:30:00",
                    "detections": [...],
                    "message": "检测到告警事件"
                }
        """
        try:
            import json
            message = json.dumps(alarm_data, ensure_ascii=False)
            total_sent = 0
            
            # 1. 向所有告警类型连接广播
            alarm_sent = await self.broadcast_to_type(message, WebSocketType.ALARMS.value)
            total_sent += alarm_sent
            
            # 2. 向特定流的订阅者广播（如果有流ID）
            stream_id = alarm_data.get("stream_id")
            if stream_id:
                stream_sent = await self.broadcast_to_stream(message, stream_id)
                # 注意：stream_sent可能与alarm_sent有重叠，这里简化处理
            
            logger.info(f"告警广播完成: alarm_id={alarm_data.get('alarm_id')}, 发送到 {alarm_sent} 个告警连接")
            return total_sent
            
        except Exception as e:
            logger.error(f"广播告警失败: {e}")
            return 0
    
    def get_connection_stats(self) -> Dict:
        """获取连接统计信息"""
        return {
            **self.connection_stats,
            "stream_connections": {
                stream_id: len(connections) 
                for stream_id, connections in self.alarm_stream_connections.items()
            },
            "active_streams": list(self.alarm_stream_connections.keys())
        }
    
    def get_connection_info(self, websocket: WebSocket) -> Dict:
        """获取连接信息"""
        return self.connection_metadata.get(websocket, {})
    
    async def subscribe_to_stream(self, websocket: WebSocket, stream_id: str):
        """订阅流"""
        try:
            metadata = self.connection_metadata.get(websocket, {})
            current_stream = metadata.get("stream_id")
            
            # 如果已经订阅了其他流，先取消订阅
            if current_stream and current_stream != stream_id:
                await self.unsubscribe_from_stream(websocket, current_stream)
            
            # 订阅新流
            if stream_id not in self.alarm_stream_connections:
                self.alarm_stream_connections[stream_id] = []
            
            if websocket not in self.alarm_stream_connections[stream_id]:
                self.alarm_stream_connections[stream_id].append(websocket)
                self.connection_stats["stream_subscriptions"] += 1
            
            # 更新元数据
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["stream_id"] = stream_id
                self.connection_metadata[websocket]["last_activity"] = datetime.now()
            
            logger.info(f"WebSocket订阅流成功: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"订阅流失败: {e}")
            return False
    
    async def unsubscribe_from_stream(self, websocket: WebSocket, stream_id: str):
        """取消订阅流"""
        try:
            if stream_id in self.alarm_stream_connections:
                if websocket in self.alarm_stream_connections[stream_id]:
                    self.alarm_stream_connections[stream_id].remove(websocket)
                    self.connection_stats["stream_subscriptions"] -= 1
                    
                    # 如果流没有连接了，删除空列表
                    if not self.alarm_stream_connections[stream_id]:
                        del self.alarm_stream_connections[stream_id]
            
            # 更新元数据
            if websocket in self.connection_metadata:
                self.connection_metadata[websocket]["stream_id"] = None
                self.connection_metadata[websocket]["last_activity"] = datetime.now()
            
            logger.info(f"WebSocket取消订阅流: {stream_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消订阅流失败: {e}")
            return False
    
    async def close_all_connections(self):
        """关闭所有连接"""
        logger.info("正在关闭所有WebSocket连接...")
        
        all_connections = []
        for connections in self.connections_by_type.values():
            all_connections.extend(connections)
        
        for connection in all_connections:
            try:
                await connection.close()
            except Exception as e:
                logger.error(f"关闭WebSocket连接失败: {e}")
        
        # 清理所有数据
        self.connections_by_type = {t.value: [] for t in WebSocketType}
        self.alarm_stream_connections.clear()
        self.connection_metadata.clear()
        self.connection_stats = {
            "total_connections": 0,
            "connections_by_type": {t.value: 0 for t in WebSocketType},
            "stream_subscriptions": 0
        }
        
        logger.info("所有WebSocket连接已关闭")

# 全局WebSocket管理器实例
unified_ws_manager = UnifiedWebSocketManager() 
websocket_manager = unified_ws_manager  # 为了兼容性，提供两个名称 