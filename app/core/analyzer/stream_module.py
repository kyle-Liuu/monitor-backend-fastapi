"""
流管理模块 - 重构自stream_manager.py
- 管理视频流生命周期
- 实现流资源复用
- 处理流状态监控
"""

import cv2
import time
import threading
import sqlite3
import json
import os
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

# 导入事件总线
from .event_bus import get_event_bus, Event

# 设置配置常量，后续可以从配置文件读取
FRAME_BUFFER_SIZE = 30
DEFAULT_FRAME_SKIP = 1
RETRY_INTERVAL = 5

logger = logging.getLogger(__name__)

class StreamModule:
    """视频流模块，处理视频流的管理和复用"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = StreamModule()
            return cls._instance
    
    def __init__(self):
        """初始化流模块"""
        # 基本属性
        self.frame_buffers = {}  # 帧缓冲区
        self.streams = {}        # 流信息缓存
        self.lock = threading.RLock()
        self.running = False
        
        # 数据库路径
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "app.db")
        
        # 流引用计数 - 用于流复用
        self.stream_ref_counts = {}  # {stream_id: count}
        
        # 流处理线程
        self.stream_threads = {}  # {stream_id: thread}
        self.stop_events = {}     # {stream_id: event}
        
        # 事件总线
        self.event_bus = get_event_bus()
    
    def start(self):
        """启动流模块"""
        if self.running:
            return True
        
        logger.info("启动流管理模块")
        self.running = True
        
        # 发布模块启动事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "stream_module",
            {"module": "stream", "status": True}
        ))
        
        # 恢复之前的流
        self._recover_streams()
        
        return True
    
    def stop(self):
        """停止流模块"""
        if not self.running:
            return True
        
        logger.info("停止流管理模块")
        
        # 停止所有流处理线程
        self._stop_all_streams()
        
        self.running = False
        
        # 发布模块停止事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "stream_module",
            {"module": "stream", "status": False}
        ))
        
        return True
    
    def _recover_streams(self):
        """恢复数据库中标记为在线的流"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有在线流
            cursor.execute("SELECT stream_id, url FROM streams WHERE status = 'active'")
            online_streams = cursor.fetchall()
            conn.close()
            
            # 启动这些流
            for stream_id, url in online_streams:
                logger.info(f"恢复流: {stream_id}")
                self.start_stream(stream_id)
                
        except Exception as e:
            logger.error(f"恢复流异常: {e}")
    
    def _stop_all_streams(self):
        """停止所有流处理线程"""
        with self.lock:
            # 复制一份流ID列表以避免在迭代过程中修改字典
            stream_ids = list(self.stream_threads.keys())
            
        # 停止每个流
        for stream_id in stream_ids:
            self.stop_stream(stream_id)
    
    def add_stream(self, stream_id: str, url: str, name: str = None, description: str = "", stream_type: str = "rtsp") -> Tuple[bool, Optional[str]]:
        """添加视频流"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute("SELECT stream_id FROM streams WHERE stream_id = ?", (stream_id,))
                if cursor.fetchone():
                    conn.close()
                    logger.warning(f"流已存在: {stream_id}")
                    return True, None  # 已存在视为成功，避免重复添加
                
                # 创建流记录
                cursor.execute(
                    """
                    INSERT INTO streams (stream_id, name, url, description, stream_type, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (stream_id, name or stream_id, url, description, stream_type, "inactive")
                )
                conn.commit()
                conn.close()
                
                # 创建帧缓冲区
                self.frame_buffers[stream_id] = {
                    "queue": [],
                    "current_frame": None,
                    "last_frame_time": 0
                }
                
                # 初始化引用计数
                self.stream_ref_counts[stream_id] = 0
                
                # 发布流添加事件
                self.event_bus.publish(Event(
                    "stream.added",
                    "stream_module",
                    {"stream_id": stream_id, "url": url}
                ))
                
                logger.info(f"添加流: {stream_id}, URL: {url}")
                return True, None
                
            except Exception as e:
                logger.error(f"添加流异常: {e}")
                return False, str(e)
    
    def remove_stream(self, stream_id: str) -> Tuple[bool, Optional[str]]:
        """移除视频流"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                # 先停止流处理
                self.stop_stream(stream_id)
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 检查是否存在
                cursor.execute("SELECT stream_id FROM streams WHERE stream_id = ?", (stream_id,))
                if not cursor.fetchone():
                    conn.close()
                    logger.warning(f"流不存在: {stream_id}")
                    return False, "流不存在"
                
                # 删除流记录
                cursor.execute("DELETE FROM streams WHERE stream_id = ?", (stream_id,))
                conn.commit()
                conn.close()
                
                # 移除帧缓冲区
                if stream_id in self.frame_buffers:
                    del self.frame_buffers[stream_id]
                
                # 移除引用计数
                if stream_id in self.stream_ref_counts:
                    del self.stream_ref_counts[stream_id]
                
                # 发布流移除事件
                self.event_bus.publish(Event(
                    "stream.removed",
                    "stream_module",
                    {"stream_id": stream_id}
                ))
                
                logger.info(f"移除流: {stream_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"移除流异常: {e}")
                return False, str(e)
    
    def start_stream(self, stream_id: str) -> Tuple[bool, Optional[str]]:
        """启动视频流处理"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 检查流是否存在
                cursor.execute("SELECT url, status FROM streams WHERE stream_id = ?", (stream_id,))
                result = cursor.fetchone()
                if not result:
                    conn.close()
                    logger.warning(f"流不存在: {stream_id}")
                    return False, "流不存在"
                
                url, status = result
                
                # 检查流是否已启动
                if stream_id in self.stream_threads and self.stream_threads[stream_id].is_alive():
                    # 更新状态
                    cursor.execute("UPDATE streams SET status = 'active' WHERE stream_id = ?", (stream_id,))
                    conn.commit()
                    conn.close()
                    logger.warning(f"流已启动: {stream_id}")
                    return True, None
                
                # 创建停止事件
                stop_event = threading.Event()
                self.stop_events[stream_id] = stop_event
                
                # 创建并启动流处理线程
                thread = threading.Thread(
                    target=self._stream_worker,
                    args=(stream_id, url, stop_event),
                    daemon=True
                )
                thread.start()
                self.stream_threads[stream_id] = thread
                
                # 更新状态
                cursor.execute(
                    """
                    UPDATE streams SET 
                    status = 'active', 
                    error_message = NULL,
                    last_online_time = CURRENT_TIMESTAMP
                    WHERE stream_id = ?
                    """, 
                    (stream_id,)
                )
                conn.commit()
                conn.close()
                
                # 发布流启动事件
                self.event_bus.publish(Event(
                    "stream.started",
                    "stream_module",
                    {"stream_id": stream_id, "url": url}
                ))
                
                logger.info(f"启动流: {stream_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"启动流异常: {e}")
                return False, str(e)
    
    def stop_stream(self, stream_id: str) -> Tuple[bool, Optional[str]]:
        """停止视频流处理"""
        if not self.running:
            return False, "模块未运行"
            
        with self.lock:
            try:
                # 检查引用计数
                ref_count = self.stream_ref_counts.get(stream_id, 0)
                if ref_count > 0:
                    logger.warning(f"流仍被引用({ref_count}次)，不能停止: {stream_id}")
                    return False, f"流仍被引用({ref_count}次)"
                
                # 设置停止事件
                if stream_id in self.stop_events:
                    self.stop_events[stream_id].set()
                
                # 等待线程结束
                if stream_id in self.stream_threads:
                    self.stream_threads[stream_id].join(timeout=5.0)
                    del self.stream_threads[stream_id]
                
                if stream_id in self.stop_events:
                    del self.stop_events[stream_id]
                
                # 更新数据库状态
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE streams SET status = 'offline' WHERE stream_id = ?", (stream_id,))
                conn.commit()
                conn.close()
                
                # 发布流停止事件
                self.event_bus.publish(Event(
                    "stream.stopped",
                    "stream_module",
                    {"stream_id": stream_id}
                ))
                
                logger.info(f"停止流: {stream_id}")
                return True, None
                
            except Exception as e:
                logger.error(f"停止流异常: {e}")
                return False, str(e)
    
    def add_consumer(self, stream_id: str, consumer_id: str) -> bool:
        """添加流消费者"""
        if not self.running:
            return False
            
        with self.lock:
            try:
                # 检查流是否存在
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT consumers FROM streams WHERE stream_id = ?", (stream_id,))
                result = cursor.fetchone()
                
                if not result:
                    conn.close()
                    logger.warning(f"流不存在: {stream_id}")
                    return False
                
                # 解析消费者列表
                consumers = []
                if result[0]:
                    try:
                        consumers = json.loads(result[0])
                    except:
                        consumers = []
                
                # 检查消费者是否已存在
                if consumer_id in consumers:
                    conn.close()
                    logger.warning(f"消费者已存在: {stream_id}/{consumer_id}")
                    return True
                
                # 添加消费者
                consumers.append(consumer_id)
                cursor.execute(
                    "UPDATE streams SET consumers = ? WHERE stream_id = ?",
                    (json.dumps(consumers), stream_id)
                )
                conn.commit()
                conn.close()
                
                # 增加引用计数
                if stream_id in self.stream_ref_counts:
                    self.stream_ref_counts[stream_id] += 1
                else:
                    self.stream_ref_counts[stream_id] = 1
                
                # 如果流未启动，启动它
                status = self.get_stream_info(stream_id).get("status")
                if status != "active":
                    self.start_stream(stream_id)
                
                # 发布消费者添加事件
                self.event_bus.publish(Event(
                    "stream.consumer_added",
                    "stream_module",
                    {"stream_id": stream_id, "consumer_id": consumer_id}
                ))
                
                logger.info(f"添加消费者: {stream_id}/{consumer_id}")
                return True
                
            except Exception as e:
                logger.error(f"添加消费者异常: {e}")
                return False
    
    def remove_consumer(self, stream_id: str, consumer_id: str) -> bool:
        """移除流消费者"""
        if not self.running:
            return False
            
        with self.lock:
            try:
                # 检查流是否存在
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT consumers FROM streams WHERE stream_id = ?", (stream_id,))
                result = cursor.fetchone()
                
                if not result:
                    conn.close()
                    logger.warning(f"流不存在: {stream_id}")
                    return False
                
                # 解析消费者列表
                consumers = []
                if result[0]:
                    try:
                        consumers = json.loads(result[0])
                    except:
                        consumers = []
                
                # 移除消费者
                if consumer_id in consumers:
                    consumers.remove(consumer_id)
                    cursor.execute(
                        "UPDATE streams SET consumers = ? WHERE stream_id = ?",
                        (json.dumps(consumers), stream_id)
                    )
                    conn.commit()
                    conn.close()
                    
                    # 减少引用计数
                    if stream_id in self.stream_ref_counts and self.stream_ref_counts[stream_id] > 0:
                        self.stream_ref_counts[stream_id] -= 1
                    
                    # 发布消费者移除事件
                    self.event_bus.publish(Event(
                        "stream.consumer_removed",
                        "stream_module",
                        {"stream_id": stream_id, "consumer_id": consumer_id}
                    ))
                    
                    logger.info(f"移除消费者: {stream_id}/{consumer_id}")
                    
                    # 如果没有消费者，停止流
                    if not consumers and self.stream_ref_counts.get(stream_id, 0) <= 0:
                        logger.info(f"流没有消费者，停止流: {stream_id}")
                        self.stop_stream(stream_id)
                    
                    return True
                else:
                    conn.close()
                    logger.warning(f"消费者不存在: {stream_id}/{consumer_id}")
                    return False
                    
            except Exception as e:
                logger.error(f"移除消费者异常: {e}")
                return False
    
    def get_stream_info(self, stream_id: str = None) -> Dict[str, Any]:
        """获取流信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if stream_id is not None:
                cursor.execute(
                    """
                    SELECT stream_id, name, url, description, stream_type, status, 
                    error_message, created_at, updated_at
                    FROM streams WHERE stream_id = ?
                    """, 
                    (stream_id,)
                )
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    return None
                # 处理消费者列表（从内存中获取）
                consumers = []
                return {
                    "stream_id": result[0],
                    "name": result[1],
                    "url": result[2],
                    "description": result[3],
                    "stream_type": result[4],
                    "status": result[5],
                    "error_message": result[6],
                    "created_at": result[7],
                    "updated_at": result[8],
                    "consumers": consumers,
                    "consumer_count": len(consumers),
                    "ref_count": self.stream_ref_counts.get(stream_id, 0),
                    "width": 0,
                    "height": 0,
                    "fps": 0
                }
            else:
                # 返回所有流信息
                cursor.execute(
                    """
                    SELECT stream_id, name, url, description, stream_type, status, 
                    error_message, created_at, updated_at
                    FROM streams
                    """
                )
                results = cursor.fetchall()
                conn.close()
                
                streams = {}
                for result in results:
                    stream_id = result[0]
                    
                    # 处理消费者列表（从内存中获取）
                    consumers = []
                    
                    streams[stream_id] = {
                        "stream_id": result[0],
                        "name": result[1],
                        "url": result[2],
                        "description": result[3],
                        "stream_type": result[4],
                        "status": result[5],
                        "error_message": result[6],
                        "created_at": result[7],
                        "updated_at": result[8],
                        "consumers": consumers,
                        "consumer_count": len(consumers),
                        "ref_count": self.stream_ref_counts.get(stream_id, 0),
                        "width": 0,
                        "height": 0,
                        "fps": 0
                    }
                
                return streams
                
        except Exception as e:
            logger.error(f"获取流信息异常: {e}")
            return {}
    
    def get_all_streams(self) -> List[Dict[str, Any]]:
        """获取所有流信息列表"""
        try:
            streams_dict = self.get_stream_info()
            if streams_dict is None:
                return []
            return list(streams_dict.values())
        except Exception as e:
            logger.error(f"获取所有流信息异常: {e}")
            return []
    
    def get_latest_frame(self, stream_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """获取最新帧信息"""
        if not self.running:
            return None, "模块未运行"
            
        with self.lock:
            try:
                if stream_id not in self.frame_buffers:
                    return None, "帧缓冲区不存在"
                
                buffer = self.frame_buffers[stream_id]
                return buffer.get("current_frame"), None
                
            except Exception as e:
                logger.error(f"获取最新帧异常: {e}")
                return None, str(e)
    
    def _stream_worker(self, stream_id: str, url: str, stop_event: threading.Event):
        """流处理线程函数"""
        try:
            logger.info(f"启动流处理线程: {stream_id}, URL: {url}")
            
            # 重试参数
            max_retries = 10
            retry_count = 0
            retry_delay = RETRY_INTERVAL
            
            # 打开视频流
            cap = None
            while retry_count < max_retries and not stop_event.is_set():
                try:
                    cap = cv2.VideoCapture(url)
                    if not cap.isOpened():
                        logger.error(f"无法打开视频流: {url}")
                        retry_count += 1
                        time.sleep(retry_delay)
                        # 指数退避策略
                        retry_delay = min(retry_delay * 2, 60)
                        continue
                    else:
                        # 重置重试计数
                        retry_count = 0
                        retry_delay = RETRY_INTERVAL
                        break
                except Exception as e:
                    logger.error(f"打开视频流异常: {e}")
                    retry_count += 1
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
            
            if not cap or not cap.isOpened() or stop_event.is_set():
                if stop_event.is_set():
                    logger.info(f"流处理线程收到停止信号: {stream_id}")
                else:
                    logger.error(f"达到最大重试次数，无法打开视频流: {url}")
                    
                    # 更新数据库流状态
                    try:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE streams SET status = 'error', error_message = ? WHERE stream_id = ?",
                            ("无法打开视频流", stream_id)
                        )
                        conn.commit()
                        conn.close()
                        
                        # 发布流错误事件
                        self.event_bus.publish(Event(
                            "stream.error",
                            "stream_module",
                            {
                                "stream_id": stream_id,
                                "error": "无法打开视频流"
                            }
                        ))
                    except Exception as e:
                        logger.error(f"更新流状态异常: {e}")
                return
            
            # 获取视频属性
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 25  # 默认帧率
            
            # 更新数据库流信息
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE streams SET 
                    status = 'active',
                    last_online_time = CURRENT_TIMESTAMP
                    WHERE stream_id = ?
                    """,
                    (stream_id,)
                )
                conn.commit()
                conn.close()
                
                # 发布流属性更新事件
                self.event_bus.publish(Event(
                    "stream.properties_updated",
                    "stream_module",
                    {
                        "stream_id": stream_id,
                        "width": width,
                        "height": height,
                        "fps": fps
                    }
                ))
            except Exception as e:
                logger.error(f"更新流状态异常: {e}")
            
            # 帧处理循环
            frame_count = 0
            buffer_size = FRAME_BUFFER_SIZE
            frame_skip = DEFAULT_FRAME_SKIP
            last_frame_time = time.time()
            last_heartbeat_time = time.time()
            actual_fps = 0
            
            while not stop_event.is_set():
                # 读取帧
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"流结束或读取错误，尝试重连: {url}")
                    cap.release()
                    
                    # 重连逻辑
                    reconnected = False
                    for retry in range(max_retries):
                        if stop_event.is_set():
                            break
                            
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 60)
                        
                        try:
                            cap = cv2.VideoCapture(url)
                            if cap.isOpened():
                                logger.info(f"重连成功: {url}")
                                reconnected = True
                                break
                        except Exception as e:
                            logger.error(f"重连异常: {e}")
                    
                    if not reconnected or stop_event.is_set():
                        logger.error(f"重连失败，达到最大重试次数: {url}")
                        
                        # 发布流错误事件
                        self.event_bus.publish(Event(
                            "stream.error",
                            "stream_module",
                            {
                                "stream_id": stream_id,
                                "error": "重连失败"
                            }
                        ))
                        break
                    continue
                
                # 跳帧处理
                frame_count += 1
                if frame_skip > 1 and frame_count % frame_skip != 0:
                    continue
                
                # 更新帧缓冲区
                with self.lock:
                    if stream_id in self.frame_buffers:
                        buffer = self.frame_buffers[stream_id]
                        
                        # 管理缓冲区大小
                        if len(buffer["queue"]) >= buffer_size:
                            # 移除最旧的帧
                            buffer["queue"].pop(0)
                        
                        # 创建帧信息
                        frame_info = {
                            "frame": frame,  # 直接存储帧数据
                            "timestamp": time.time(),
                            "frame_id": frame_count,
                            "width": width,
                            "height": height,
                            "shape": frame.shape,
                            "dtype": str(frame.dtype)
                        }
                        
                        buffer["queue"].append(frame_info)
                        buffer["current_frame"] = frame_info
                        buffer["last_frame_time"] = time.time()
                        
                        self.frame_buffers[stream_id] = buffer
                
                # 计算实际帧率
                now = time.time()
                if now - last_frame_time >= 1.0:
                    actual_fps = frame_count / (now - last_frame_time)
                    frame_count = 0
                    last_frame_time = now
                
                # 发送心跳事件
                if now - last_heartbeat_time >= 5.0:
                    # 每5秒更新一次数据库状态和发送心跳
                    try:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE streams SET 
                            status = 'active',
                            last_online_time = CURRENT_TIMESTAMP
                            WHERE stream_id = ?
                            """,
                            (stream_id,)
                        )
                        conn.commit()
                        conn.close()
                        
                        # 发布流心跳事件
                        self.event_bus.publish(Event(
                            "stream.heartbeat",
                            "stream_module",
                            {
                                "stream_id": stream_id,
                                "fps": actual_fps,
                                "frame_count": frame_count
                            }
                        ))
                        
                        last_heartbeat_time = now
                    except Exception as e:
                        logger.error(f"更新流状态异常: {e}")
                
                # 控制帧率
                target_frame_time = 1.0 / fps
                elapsed = now - last_frame_time
                if elapsed < target_frame_time:
                    time.sleep(target_frame_time - elapsed)
            
            # 清理资源
            if cap:
                cap.release()
            
            logger.info(f"流处理线程退出: {stream_id}")
        
        except Exception as e:
            logger.error(f"流处理线程异常: {stream_id}, {e}", exc_info=True)
            
            # 更新数据库流状态
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE streams SET status = 'error', error_message = ? WHERE stream_id = ?",
                    (str(e), stream_id)
                )
                conn.commit()
                conn.close()
                
                # 发布流错误事件
                self.event_bus.publish(Event(
                    "stream.error",
                    "stream_module",
                    {
                        "stream_id": stream_id,
                        "error": str(e)
                    }
                ))
            except Exception as db_error:
                logger.error(f"更新流状态异常: {db_error}")

# 全局流模块实例
def get_stream_module():
    """获取全局流模块实例"""
    return StreamModule.get_instance() 