"""
输出模块
- 处理分析结果输出
- 管理RTMP推流
- 实现视频录制
"""

import os
import sys
import cv2
import time
import threading
import queue
import json
import sqlite3
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

# 导入事件总线
from .event_bus import get_event_bus, Event

logger = logging.getLogger(__name__)

class OutputModule:
    """输出模块，处理分析结果输出和视频推流"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = OutputModule()
            return cls._instance
    
    def __init__(self):
        """初始化输出模块"""
        # 基本属性
        self.running = False
        self.lock = threading.RLock()
        
        # 数据库路径
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "app.db")
        
        # 输出队列 - {output_id: queue.Queue}
        self.output_queues = {}
        
        # 输出线程 - {output_id: threading.Thread}
        self.output_threads = {}
        self.stop_events = {}  # {output_id: threading.Event}
        
        # 结果缓存 - {task_id: last_result}
        self.result_cache = {}
        
        # 事件总线
        self.event_bus = get_event_bus()
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 监听任务结果事件
        self.event_bus.subscribe("task.result", self._handle_task_result)
        
        # 监听任务删除事件
        self.event_bus.subscribe("task.removed", self._handle_task_removed)
    
    def _handle_task_result(self, event: Event):
        """处理任务结果事件"""
        # 提取任务信息
        task_id = event.data.get("task_id")
        result = event.data.get("result")
        
        if not task_id or not result:
            return
        
        # 更新结果缓存
        with self.lock:
            self.result_cache[task_id] = result
        
        # 将结果放入对应的输出队列
        self._push_result_to_outputs(task_id, result)
    
    def _handle_task_removed(self, event: Event):
        """处理任务删除事件"""
        task_id = event.data.get("task_id")
        if not task_id:
            return
        
        # 清理结果缓存
        with self.lock:
            if task_id in self.result_cache:
                del self.result_cache[task_id]
    
    def _push_result_to_outputs(self, task_id: str, result: Dict):
        """将结果推送到关联的输出队列"""
        try:
            # 查询关联的输出
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT output_id FROM outputs 
                WHERE task_id = ? AND enabled = 1
                """,
                (task_id,)
            )
            
            outputs = cursor.fetchall()
            conn.close()
            
            if not outputs:
                return
            
            # 推送到每个输出队列
            with self.lock:
                for (output_id,) in outputs:
                    if output_id in self.output_queues:
                        # 检查队列是否已满
                        queue = self.output_queues[output_id]
                        
                        try:
                            if not queue.full():
                                queue.put_nowait(result)
                            else:
                                # 队列满，丢弃旧结果
                                try:
                                    queue.get_nowait()
                                    queue.put_nowait(result)
                                except:
                                    pass
                        except:
                            pass
            
        except Exception as e:
            logger.error(f"推送结果到输出异常: {e}")
    
    def start(self):
        """启动输出模块"""
        if self.running:
            return True
        
        logger.info("启动输出模块")
        self.running = True
        
        # 恢复现有输出
        self._recover_outputs()
        
        # 发布模块启动事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "output_module",
            {"module": "output", "status": True}
        ))
        
        return True
    
    def stop(self):
        """停止输出模块"""
        if not self.running:
            return True
        
        logger.info("停止输出模块")
        
        # 停止所有输出
        self._stop_all_outputs()
        
        self.running = False
        
        # 发布模块停止事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "output_module",
            {"module": "output", "status": False}
        ))
        
        return True
    
    def _recover_outputs(self):
        """恢复数据库中启用的输出"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有启用的输出
            cursor.execute(
                """
                SELECT output_id, task_id, url, type, config 
                FROM outputs 
                WHERE enabled = 1
                """
            )
            
            outputs = cursor.fetchall()
            conn.close()
            
            # 启动这些输出
            for output_id, task_id, url, output_type, config_str in outputs:
                try:
                    config = json.loads(config_str) if config_str else {}
                    logger.info(f"恢复输出: {output_id}")
                    
                    self.create_output(output_id, task_id, url, output_type, config)
                except Exception as e:
                    logger.error(f"恢复输出失败: {output_id}, {e}")
            
        except Exception as e:
            logger.error(f"恢复输出异常: {e}")
    
    def _stop_all_outputs(self):
        """停止所有输出"""
        with self.lock:
            # 获取所有输出ID
            output_ids = list(self.output_threads.keys())
        
        # 停止每个输出
        for output_id in output_ids:
            self.stop_output(output_id)
    
    def create_output(self, output_id: str, task_id: str, url: str, output_type: str = "rtmp", config: Dict = None) -> Tuple[bool, Optional[str]]:
        """创建输出
        
        Args:
            output_id: 输出ID
            task_id: 关联的任务ID
            url: 输出URL
            output_type: 输出类型，如 'rtmp', 'file'
            config: 输出配置
            
        Returns:
            (成功标志, 错误消息)
        """
        if not self.running:
            return False, "模块未运行"
        
        with self.lock:
            try:
                # 检查输出是否已存在
                if output_id in self.output_threads and self.output_threads[output_id].is_alive():
                    logger.warning(f"输出已存在: {output_id}")
                    return False, "输出已存在"
                
                # 创建配置
                if config is None:
                    config = {}
                
                # 保存到数据库
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO outputs 
                    (output_id, task_id, url, type, config, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (output_id, task_id, url, output_type, json.dumps(config), 1)
                )
                conn.commit()
                conn.close()
                
                # 创建输出队列
                self.output_queues[output_id] = queue.Queue(maxsize=10)
                
                # 创建停止事件
                stop_event = threading.Event()
                self.stop_events[output_id] = stop_event
                
                # 创建并启动输出线程
                thread = threading.Thread(
                    target=self._output_worker,
                    args=(output_id, task_id, url, output_type, config, stop_event),
                    daemon=True
                )
                thread.start()
                
                # 保存线程引用
                self.output_threads[output_id] = thread
                
                # 发布输出创建事件
                self.event_bus.publish(Event(
                    "output.created",
                    "output_module",
                    {
                        "output_id": output_id,
                        "task_id": task_id,
                        "url": url,
                        "type": output_type
                    }
                ))
                
                logger.info(f"创建输出: {output_id}, 任务: {task_id}, URL: {url}")
                return True, None
                
            except Exception as e:
                logger.error(f"创建输出异常: {e}")
                return False, str(e)
    
    def stop_output(self, output_id: str) -> Tuple[bool, Optional[str]]:
        """停止输出"""
        if not self.running:
            return False, "模块未运行"
        
        try:
            with self.lock:
                # 检查输出是否存在
                if output_id not in self.output_threads:
                    logger.warning(f"输出不存在: {output_id}")
                    return False, "输出不存在"
                
                # 设置停止事件
                if output_id in self.stop_events:
                    self.stop_events[output_id].set()
                
                # 等待线程结束
                if output_id in self.output_threads:
                    self.output_threads[output_id].join(timeout=5.0)
                    del self.output_threads[output_id]
                
                # 清理资源
                if output_id in self.stop_events:
                    del self.stop_events[output_id]
                
                if output_id in self.output_queues:
                    del self.output_queues[output_id]
                
                # 更新数据库
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE outputs SET enabled = 0 WHERE output_id = ?",
                    (output_id,)
                )
                conn.commit()
                conn.close()
                
                # 发布输出停止事件
                self.event_bus.publish(Event(
                    "output.stopped",
                    "output_module",
                    {"output_id": output_id}
                ))
                
                logger.info(f"停止输出: {output_id}")
                return True, None
                
        except Exception as e:
            logger.error(f"停止输出异常: {e}")
            return False, str(e)
    
    def get_output_info(self, output_id: str = None) -> Dict:
        """获取输出信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if output_id:
                # 获取特定输出信息
                cursor.execute(
                    """
                    SELECT output_id, task_id, url, type, config, enabled, 
                    created_at, updated_at
                    FROM outputs WHERE output_id = ?
                    """, 
                    (output_id,)
                )
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    return {}
                
                # 检查线程是否活跃
                is_active = (
                    output_id in self.output_threads and 
                    self.output_threads[output_id].is_alive()
                )
                
                return {
                    "output_id": result[0],
                    "task_id": result[1],
                    "url": result[2],
                    "type": result[3],
                    "config": json.loads(result[4]) if result[4] else {},
                    "enabled": bool(result[5]),
                    "created_at": result[6],
                    "updated_at": result[7],
                    "active": is_active
                }
            else:
                # 获取所有输出信息
                cursor.execute(
                    """
                    SELECT output_id, task_id, url, type, config, enabled, 
                    created_at, updated_at
                    FROM outputs
                    """
                )
                results = cursor.fetchall()
                conn.close()
                
                outputs = {}
                for row in results:
                    output_id = row[0]
                    
                    # 检查线程是否活跃
                    is_active = (
                        output_id in self.output_threads and 
                        self.output_threads[output_id].is_alive()
                    )
                    
                    outputs[output_id] = {
                        "output_id": output_id,
                        "task_id": row[1],
                        "url": row[2],
                        "type": row[3],
                        "config": json.loads(row[4]) if row[4] else {},
                        "enabled": bool(row[5]),
                        "created_at": row[6],
                        "updated_at": row[7],
                        "active": is_active
                    }
                
                return outputs
                
        except Exception as e:
            logger.error(f"获取输出信息异常: {e}")
            return {}
    
    def _output_worker(self, output_id: str, task_id: str, url: str, output_type: str, config: Dict, stop_event: threading.Event):
        """输出工作线程"""
        try:
            logger.info(f"启动输出线程: {output_id}, URL: {url}")
            
            # 根据输出类型初始化不同的输出处理
            if output_type == "rtmp":
                self._rtmp_output_worker(output_id, task_id, url, config, stop_event)
            elif output_type == "file":
                self._file_output_worker(output_id, task_id, url, config, stop_event)
            else:
                logger.error(f"不支持的输出类型: {output_type}")
                return
                
        except Exception as e:
            logger.error(f"输出线程异常: {e}")
            
            # 发布错误事件
            self.event_bus.publish(Event(
                "output.error",
                "output_module",
                {
                    "output_id": output_id,
                    "error": str(e)
                }
            ))
    
    def _rtmp_output_worker(self, output_id: str, task_id: str, url: str, config: Dict, stop_event: threading.Event):
        """RTMP输出工作线程"""
        # 视频编码器
        fourcc = cv2.VideoWriter_fourcc(*'XVID')  # 或 'H264'，根据需要选择
        writer = None
        frame_width = config.get("width", 1280)
        frame_height = config.get("height", 720)
        fps = config.get("fps", 25)
        
        try:
            # 创建视频写入器
            writer = cv2.VideoWriter(
                url,
                fourcc,
                fps,
                (frame_width, frame_height)
            )
            
            if not writer.isOpened():
                logger.error(f"无法打开RTMP输出: {url}")
                return
            
            # 获取输出队列
            output_queue = self.output_queues.get(output_id)
            if not output_queue:
                logger.error(f"输出队列不存在: {output_id}")
                return
            
            # 主循环
            while not stop_event.is_set():
                try:
                    # 尝试从队列获取结果，最多等待100ms
                    result = output_queue.get(timeout=0.1)
                    
                    # 提取帧和检测结果
                    frame = result.get("frame")
                    detections = result.get("objects", [])
                    
                    if frame is None:
                        continue
                    
                    # 调整帧大小
                    if frame.shape[1] != frame_width or frame.shape[0] != frame_height:
                        frame = cv2.resize(frame, (frame_width, frame_height))
                    
                    # 绘制检测框
                    for det in detections:
                        label = det.get("label", "")
                        confidence = det.get("confidence", 0)
                        box = det.get("bbox", [0, 0, 0, 0])
                        
                        # 绘制边界框
                        x1, y1, x2, y2 = box
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                        
                        # 绘制标签
                        text = f"{label}: {confidence:.2f}"
                        cv2.putText(frame, text, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 写入帧
                    writer.write(frame)
                    
                except queue.Empty:
                    # 队列为空，继续等待
                    continue
                except Exception as e:
                    logger.error(f"处理输出帧异常: {e}")
                    time.sleep(1)  # 错误后延迟
            
            logger.info(f"RTMP输出线程退出: {output_id}")
            
        except Exception as e:
            logger.error(f"RTMP输出异常: {e}")
        finally:
            # 清理资源
            if writer:
                writer.release()
    
    def _file_output_worker(self, output_id: str, task_id: str, file_path: str, config: Dict, stop_event: threading.Event):
        """文件输出工作线程"""
        # 视频编码器
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = None
        frame_width = config.get("width", 1280)
        frame_height = config.get("height", 720)
        fps = config.get("fps", 25)
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # 创建视频写入器
            writer = cv2.VideoWriter(
                file_path,
                fourcc,
                fps,
                (frame_width, frame_height)
            )
            
            if not writer.isOpened():
                logger.error(f"无法打开文件输出: {file_path}")
                return
            
            # 获取输出队列
            output_queue = self.output_queues.get(output_id)
            if not output_queue:
                logger.error(f"输出队列不存在: {output_id}")
                return
            
            # 主循环
            while not stop_event.is_set():
                try:
                    # 尝试从队列获取结果，最多等待100ms
                    result = output_queue.get(timeout=0.1)
                    
                    # 提取帧和检测结果
                    frame = result.get("frame")
                    detections = result.get("objects", [])
                    
                    if frame is None:
                        continue
                    
                    # 调整帧大小
                    if frame.shape[1] != frame_width or frame.shape[0] != frame_height:
                        frame = cv2.resize(frame, (frame_width, frame_height))
                    
                    # 绘制检测框
                    for det in detections:
                        label = det.get("label", "")
                        confidence = det.get("confidence", 0)
                        box = det.get("bbox", [0, 0, 0, 0])
                        
                        # 绘制边界框
                        x1, y1, x2, y2 = box
                        cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                        
                        # 绘制标签
                        text = f"{label}: {confidence:.2f}"
                        cv2.putText(frame, text, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # 写入帧
                    writer.write(frame)
                    
                except queue.Empty:
                    # 队列为空，继续等待
                    continue
                except Exception as e:
                    logger.error(f"处理输出帧异常: {e}")
                    time.sleep(1)  # 错误后延迟
            
            logger.info(f"文件输出线程退出: {output_id}")
            
        except Exception as e:
            logger.error(f"文件输出异常: {e}")
        finally:
            # 清理资源
            if writer:
                writer.release()

# 全局输出模块实例
def get_output_module():
    """获取全局输出模块实例"""
    return OutputModule.get_instance() 