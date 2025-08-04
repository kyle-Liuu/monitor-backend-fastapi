"""
WebSocket状态更新接口
用于实时推送系统状态和任务状态
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict
import json
import logging
import asyncio
from datetime import datetime

from app.core.websocket_manager import unified_ws_manager, WebSocketType
from app.core.analyzer.analyzer_service import AnalyzerService

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/status")
async def status_websocket(websocket: WebSocket):
    """状态WebSocket连接"""
    # 使用统一的WebSocket管理器
    success = await unified_ws_manager.connect(
        websocket, 
        WebSocketType.STATUS.value,
        client_info={"endpoint": "status"}
    )
    
    if not success:
        logger.error("状态WebSocket连接建立失败")
        return
    
    try:
        # 获取分析器服务实例
        analyzer_service = AnalyzerService.get_instance()
        
        # 发送初始状态
        initial_status = analyzer_service.get_task_status()
        initial_message = {
            "type": "initial_status",
            "data": initial_status,
            "timestamp": int(asyncio.get_event_loop().time()),
            "server_time": datetime.now().isoformat()
        }
        
        await unified_ws_manager.send_personal_message(
            json.dumps(initial_message), 
            websocket
        )
        
        logger.info("状态WebSocket发送初始状态完成")
        
        # 保持连接，等待状态广播和客户端消息
        while True:
            try:
                # 接收客户端消息（如心跳、状态请求等）
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                if message.get("type") == "ping":
                    # 心跳响应
                    pong_message = {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                        "server_time": int(asyncio.get_event_loop().time())
                    }
                    await unified_ws_manager.send_personal_message(
                        json.dumps(pong_message), 
                        websocket
                    )
                    
                elif message.get("type") == "request_status":
                    # 请求当前状态
                    current_status = analyzer_service.get_task_status()
                    status_message = {
                        "type": "status_update",
                        "data": current_status,
                        "timestamp": int(asyncio.get_event_loop().time()),
                        "server_time": datetime.now().isoformat()
                    }
                    await unified_ws_manager.send_personal_message(
                        json.dumps(status_message), 
                        websocket
                    )
                    
                elif message.get("type") == "request_stats":
                    # 请求连接统计
                    stats = unified_ws_manager.get_connection_stats()
                    stats_message = {
                        "type": "connection_stats",
                        "data": stats,
                        "timestamp": int(asyncio.get_event_loop().time()),
                        "server_time": datetime.now().isoformat()
                    }
                    await unified_ws_manager.send_personal_message(
                        json.dumps(stats_message), 
                        websocket
                    )
                
                else:
                    # 未知消息类型
                    error_message = {
                        "type": "error",
                        "message": f"未知的消息类型: {message.get('type')}",
                        "timestamp": datetime.now().isoformat()
                    }
                    await unified_ws_manager.send_personal_message(
                        json.dumps(error_message), 
                        websocket
                    )
            
            except asyncio.TimeoutError:
                # 可以在这里处理超时逻辑
                continue
                
    except WebSocketDisconnect:
        unified_ws_manager.disconnect(websocket)
        logger.info("状态WebSocket连接正常断开")
        
    except Exception as e:
        logger.error(f"状态WebSocket异常: {e}")
        unified_ws_manager.disconnect(websocket)

# 状态广播函数（供其他模块调用）
async def broadcast_status_update(status_data: Dict):
    """广播状态更新到所有状态WebSocket连接"""
    try:
        message = {
            "type": "status_update", 
            "data": status_data,
            "timestamp": int(asyncio.get_event_loop().time()),
            "server_time": datetime.now().isoformat()
        }
        
        sent_count = await unified_ws_manager.broadcast_to_type(
            json.dumps(message), 
            WebSocketType.STATUS.value
        )
        
        logger.debug(f"状态更新广播完成，发送到 {sent_count} 个连接")
        return sent_count
        
    except Exception as e:
        logger.error(f"状态更新广播失败: {e}")
        return 0

# 系统状态定时广播任务
async def status_broadcast_task():
    """定时广播系统状态的后台任务"""
    logger.info("状态广播任务启动")
    
    while True:
        try:
            # 检查是否有状态WebSocket连接
            stats = unified_ws_manager.get_connection_stats()
            status_connections = stats["connections_by_type"].get(WebSocketType.STATUS.value, 0)
            
            if status_connections > 0:
                # 获取当前状态
                analyzer_service = AnalyzerService.get_instance()
                current_status = analyzer_service.get_task_status()
                
                # 广播状态更新
                await broadcast_status_update(current_status)
            
            # 等待5秒后下次广播
            await asyncio.sleep(5)
            
        except asyncio.CancelledError:
            logger.info("状态广播任务被取消")
            break
        except Exception as e:
            logger.error(f"状态广播任务异常: {e}", exc_info=True)
            await asyncio.sleep(5)  # 错误后休眠

# 连接统计广播（可选）
async def broadcast_connection_stats():
    """广播连接统计信息"""
    try:
        stats = unified_ws_manager.get_connection_stats()
        message = {
            "type": "connection_stats",
            "data": stats,
            "timestamp": int(asyncio.get_event_loop().time()),
            "server_time": datetime.now().isoformat()
        }
        
        sent_count = await unified_ws_manager.broadcast_to_type(
            json.dumps(message),
            WebSocketType.STATUS.value
        )
        
        logger.debug(f"连接统计广播完成，发送到 {sent_count} 个连接")
        return sent_count
        
    except Exception as e:
        logger.error(f"连接统计广播失败: {e}")
        return 0