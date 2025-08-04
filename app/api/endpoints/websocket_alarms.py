"""
WebSocket报警触发接口
用于实时触发报警视频保存
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List
import json
import logging
import asyncio
from datetime import datetime

from app.core.video_recorder import video_recorder

logger = logging.getLogger(__name__)
router = APIRouter()

class AlarmWebSocketManager:
    """报警WebSocket管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.stream_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, stream_id: str = None, accept_connection: bool = True):
        """连接WebSocket"""
        if accept_connection:
            await websocket.accept()
        
        self.active_connections.append(websocket)
        
        if stream_id:
            if stream_id not in self.stream_connections:
                self.stream_connections[stream_id] = []
            self.stream_connections[stream_id].append(websocket)
        
        logger.info(f"WebSocket连接建立，总连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, stream_id: str = None):
        """断开WebSocket连接"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        if stream_id and stream_id in self.stream_connections:
            if websocket in self.stream_connections[stream_id]:
                self.stream_connections[stream_id].remove(websocket)
        
        logger.info(f"WebSocket连接断开，总连接数: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """广播消息"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)
    
    async def broadcast_to_stream(self, message: str, stream_id: str):
        """向特定流广播消息"""
        if stream_id not in self.stream_connections:
            return
        
        disconnected = []
        for connection in self.stream_connections[stream_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"向流广播消息失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection, stream_id)

# 全局WebSocket管理器
alarm_ws_manager = AlarmWebSocketManager()

@router.websocket("/alarms")
async def alarm_websocket(websocket: WebSocket):
    """报警WebSocket连接"""
    await alarm_ws_manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理不同类型的消息
            if message["type"] == "alarm_detected":
                await handle_alarm_detected(message, websocket)
            elif message["type"] == "subscribe_stream":
                await handle_subscribe_stream(message, websocket)
            elif message["type"] == "ping":
                await alarm_ws_manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}),
                    websocket
                )
                
    except WebSocketDisconnect:
        alarm_ws_manager.disconnect(websocket)
        logger.info("报警WebSocket连接断开")
    except Exception as e:
        logger.error(f"报警WebSocket异常: {e}")
        alarm_ws_manager.disconnect(websocket)

async def handle_alarm_detected(message: Dict, websocket: WebSocket):
    """处理报警检测消息"""
    try:
        stream_id = message.get("stream_id")
        alarm_id = message.get("alarm_id")
        pre_seconds = message.get("pre_seconds", 1)
        post_seconds = message.get("post_seconds", 1)
        
        logger.info(f"WebSocket报警检测: stream_id={stream_id}, alarm_id={alarm_id}")
        
        if not stream_id or not alarm_id:
            await alarm_ws_manager.send_personal_message(
                json.dumps({
                    "type": "error",
                    "message": "缺少必要参数：stream_id 或 alarm_id"
                }),
                websocket
            )
            return
        
        # 调试信息：检查录制状态
        recording_streams = list(video_recorder.recording_streams.keys())
        logger.info(f"WebSocket当前录制流: {recording_streams}")
        logger.info(f"WebSocket流 {stream_id} 是否在录制: {stream_id in video_recorder.recording_streams}")
        
        if stream_id in video_recorder.recording_streams:
            status = video_recorder.get_recording_status(stream_id)
            segments = video_recorder.get_available_segments(stream_id)
            logger.info(f"WebSocket流状态: {status.get('status')}, 段数: {len(segments)}")
        
        # 保存报警视频
        video_path = await video_recorder.save_alarm_video(
            stream_id=stream_id,
            alarm_id=alarm_id,
            pre_seconds=pre_seconds,
            post_seconds=post_seconds
        )
        
        if video_path:
            # 发送成功消息
            success_message = {
                "type": "alarm_video_saved",
                "alarm_id": alarm_id,
                "stream_id": stream_id,
                "video_path": video_path,
                "pre_seconds": pre_seconds,
                "post_seconds": post_seconds,
                "saved_time": datetime.now().isoformat()
            }
            
            # 向所有连接广播
            await alarm_ws_manager.broadcast(json.dumps(success_message))
            
            # 向特定流广播
            await alarm_ws_manager.broadcast_to_stream(
                json.dumps(success_message), 
                stream_id
            )
            
            logger.info(f"报警视频保存成功: {alarm_id} -> {video_path}")
        else:
            # 发送失败消息
            error_message = {
                "type": "alarm_video_save_failed",
                "alarm_id": alarm_id,
                "stream_id": stream_id,
                "error": "保存报警视频失败"
            }
            
            await alarm_ws_manager.send_personal_message(
                json.dumps(error_message),
                websocket
            )
            
            logger.error(f"报警视频保存失败: {alarm_id}")
            
    except Exception as e:
        logger.error(f"处理报警检测消息失败: {e}")
        await alarm_ws_manager.send_personal_message(
            json.dumps({
                "type": "error",
                "message": f"处理报警检测消息失败: {str(e)}"
            }),
            websocket
        )

async def handle_subscribe_stream(message: Dict, websocket: WebSocket):
    """处理订阅流消息"""
    try:
        stream_id = message.get("stream_id")
        
        if not stream_id:
            await alarm_ws_manager.send_personal_message(
                json.dumps({
                    "type": "error",
                    "message": "缺少必要参数：stream_id"
                }),
                websocket
            )
            return
        
        # 重新连接WebSocket到特定流（不重复accept）
        alarm_ws_manager.disconnect(websocket)
        await alarm_ws_manager.connect(websocket, stream_id, accept_connection=False)
        
        # 发送订阅成功消息
        await alarm_ws_manager.send_personal_message(
            json.dumps({
                "type": "stream_subscribed",
                "stream_id": stream_id,
                "timestamp": datetime.now().isoformat()
            }),
            websocket
        )
        
        logger.info(f"WebSocket订阅流成功: {stream_id}")
        
    except Exception as e:
        logger.error(f"处理订阅流消息失败: {e}")
        await alarm_ws_manager.send_personal_message(
            json.dumps({
                "type": "error",
                "message": f"处理订阅流消息失败: {str(e)}"
            }),
            websocket
        )

# 触发报警视频保存的函数（供其他模块调用）
async def trigger_alarm_video_save(stream_id: str, alarm_id: str, 
                                 pre_seconds: int = 1, post_seconds: int = 1):
    """触发报警视频保存"""
    try:
        # 保存报警视频
        video_path = await video_recorder.save_alarm_video(
            stream_id=stream_id,
            alarm_id=alarm_id,
            pre_seconds=pre_seconds,
            post_seconds=post_seconds
        )
        
        if video_path:
            # 构造消息
            message = {
                "type": "alarm_video_saved",
                "alarm_id": alarm_id,
                "stream_id": stream_id,
                "video_path": video_path,
                "pre_seconds": pre_seconds,
                "post_seconds": post_seconds,
                "saved_time": datetime.now().isoformat()
            }
            
            # 广播消息
            await alarm_ws_manager.broadcast(json.dumps(message))
            await alarm_ws_manager.broadcast_to_stream(json.dumps(message), stream_id)
            
            logger.info(f"触发报警视频保存成功: {alarm_id} -> {video_path}")
            return video_path
        else:
            logger.error(f"触发报警视频保存失败: {alarm_id}")
            return None
            
    except Exception as e:
        logger.error(f"触发报警视频保存异常: {e}")
        return None 