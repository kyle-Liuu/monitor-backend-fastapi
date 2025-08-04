"""
告警管理模块
- 处理告警事件
- 告警数据存储与检索
- 告警推送机制
"""

import os
import sys
import time
import threading
import queue
import json
import sqlite3
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# 导入事件总线
from .event_bus import get_event_bus, Event

logger = logging.getLogger(__name__)

class AlarmModule:
    """告警管理模块，处理告警事件和通知"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = AlarmModule()
            return cls._instance
    
    def __init__(self):
        """初始化告警模块"""
        # 基本属性
        self.running = False
        self.lock = threading.RLock()
        
        # 数据库路径
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "app.db")
        
        # 告警队列
        self.alarm_queue = queue.Queue()
        
        # 告警处理线程
        self.alarm_thread = None
        self.stop_event = threading.Event()
        
        # 告警缓存 - 避免重复告警
        self.alarm_cache = {}  # {alarm_key: timestamp}
        self.alarm_cache_ttl = 60  # 60秒内相同告警不重复触发
        
        # 事件总线
        self.event_bus = get_event_bus()
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 监听算法检测结果事件
        self.event_bus.subscribe("algorithm.inference_completed", self._handle_algorithm_result)
        
        # 监听任务结果事件
        self.event_bus.subscribe("task.result", self._handle_task_result)
    
    def _handle_algorithm_result(self, event: Event):
        """处理算法检测结果事件"""
        # 检查是否包含告警数据
        if not event.data or "inference_time" not in event.data:
            return
        
        # 提取数据
        task_id = event.data.get("task_id")
        algo_id = event.data.get("algo_id")
        stream_id = event.data.get("stream_id")
        
        # TODO: 根据算法推理结果判断是否需要触发告警
    
    def _handle_task_result(self, event: Event):
        """处理任务结果事件"""
        # 提取任务信息
        task_id = event.data.get("task_id")
        result = event.data.get("result")
        
        if not task_id or not result:
            return
        
        # 检查结果中是否包含告警
        objects = result.get("objects", [])
        if not objects:
            return
        
        # 处理每个检测对象
        for obj in objects:
            # 检查是否需要触发告警
            if self._should_trigger_alarm(task_id, obj):
                # 创建告警数据
                alarm_data = self._create_alarm_data(task_id, obj, result)
                
                # 放入告警队列
                self.alarm_queue.put(alarm_data)
    
    def _should_trigger_alarm(self, task_id: str, obj: Dict) -> bool:
        """判断是否需要触发告警
        
        Args:
            task_id: 任务ID
            obj: 检测对象
            
        Returns:
            是否触发告警
        """
        # 获取告警配置
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alarm_config FROM tasks 
                WHERE task_id = ?
                """,
                (task_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return False
            
            alarm_config = json.loads(result[0]) if result[0] else {}
            
            # 配置为空时使用默认配置
            if not alarm_config:
                # 默认告警配置 - 可以根据实际需求调整
                alarm_config = {
                    "enabled": True,
                    "confidence_threshold": 0.5,
                    "classes": [],  # 空列表表示所有类别都会触发
                    "cooldown": self.alarm_cache_ttl
                }
            
            # 检查告警是否启用
            if not alarm_config.get("enabled", True):
                return False
            
            # 检查置信度是否超过阈值
            confidence = obj.get("confidence", 0)
            confidence_threshold = alarm_config.get("confidence_threshold", 0.5)
            if confidence < confidence_threshold:
                return False
            
            # 检查类别是否需要告警
            label = obj.get("label", "")
            alarm_classes = alarm_config.get("classes", [])
            if alarm_classes and label not in alarm_classes:
                return False
            
            # 检查是否在冷却期内
            cooldown = alarm_config.get("cooldown", self.alarm_cache_ttl)
            alarm_key = f"{task_id}_{label}"
            
            with self.lock:
                if alarm_key in self.alarm_cache:
                    last_time = self.alarm_cache[alarm_key]
                    if time.time() - last_time < cooldown:
                        return False
                    
                # 更新最后告警时间
                self.alarm_cache[alarm_key] = time.time()
            
            return True
            
        except Exception as e:
            logger.error(f"检查告警条件异常: {e}")
            return False
    
    def _create_alarm_data(self, task_id: str, obj: Dict, result: Dict) -> Dict:
        """创建告警数据
        
        Args:
            task_id: 任务ID
            obj: 检测对象
            result: 完整结果
            
        Returns:
            告警数据
        """
        # 生成告警ID
        alarm_id = f"alarm_{str(uuid.uuid4())[:8]}"
        
        # 获取任务信息
        stream_id = result.get("stream_id", "")
        frame_id = result.get("frame_id", 0)
        timestamp = result.get("timestamp", time.time())
        
        # 获取对象信息
        label = obj.get("label", "")
        confidence = obj.get("confidence", 0)
        bbox = obj.get("bbox", [0, 0, 0, 0])
        
        # 创建告警数据
        alarm_data = {
            "alarm_id": alarm_id,
            "task_id": task_id,
            "stream_id": stream_id,
            "label": label,
            "confidence": confidence,
            "bbox": bbox,
            "frame_id": frame_id,
            "timestamp": timestamp,
            "created_at": time.time(),
            "status": "new",  # new, processed, ignored
            "level": self._calculate_alarm_level(label, confidence),
            "image_path": None,  # 将在保存图像后更新
            "video_path": None   # 将在保存视频后更新
        }
        
        return alarm_data
    
    def _calculate_alarm_level(self, label: str, confidence: float) -> str:
        """计算告警级别
        
        Args:
            label: 标签
            confidence: 置信度
            
        Returns:
            告警级别: 'low', 'medium', 'high'
        """
        # 根据置信度判断级别
        if confidence < 0.6:
            return "low"
        elif confidence < 0.8:
            return "medium"
        else:
            return "high"
    
    def start(self):
        """启动告警模块"""
        if self.running:
            return True
        
        logger.info("启动告警管理模块")
        self.running = True
        
        # 清空停止事件
        self.stop_event.clear()
        
        # 启动告警处理线程
        self.alarm_thread = threading.Thread(
            target=self._alarm_worker,
            daemon=True
        )
        self.alarm_thread.start()
        
        # 发布模块启动事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "alarm_module",
            {"module": "alarm", "status": True}
        ))
        
        return True
    
    def stop(self):
        """停止告警模块"""
        if not self.running:
            return True
        
        logger.info("停止告警管理模块")
        
        # 设置停止事件
        self.stop_event.set()
        
        # 等待线程结束
        if self.alarm_thread and self.alarm_thread.is_alive():
            self.alarm_thread.join(timeout=5.0)
        
        self.running = False
        
        # 发布模块停止事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "alarm_module",
            {"module": "alarm", "status": False}
        ))
        
        return True
    
    def _alarm_worker(self):
        """告警处理线程函数"""
        logger.info("告警处理线程已启动")
        
        while not self.stop_event.is_set():
            try:
                # 从队列获取告警，最多等待1秒
                try:
                    alarm_data = self.alarm_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # 处理告警
                self._process_alarm(alarm_data)
                
                # 标记任务完成
                self.alarm_queue.task_done()
                
            except Exception as e:
                logger.error(f"处理告警异常: {e}")
        
        logger.info("告警处理线程已退出")
    
    def _process_alarm(self, alarm_data: Dict):
        """处理告警
        
        Args:
            alarm_data: 告警数据
        """
        try:
            # 保存告警到数据库
            self._save_alarm(alarm_data)
            
            # 保存告警图像
            image_path = self._save_alarm_image(alarm_data)
            if image_path:
                alarm_data["image_path"] = image_path
                
                # 更新数据库中的图像路径
                self._update_alarm_image_path(alarm_data["alarm_id"], image_path)
            
            # 发布告警事件
            self.event_bus.publish(Event(
                "alarm.triggered",
                "alarm_module",
                alarm_data
            ))
            
            logger.info(f"触发告警: {alarm_data['alarm_id']}, 类型: {alarm_data['label']}, 级别: {alarm_data['level']}")
            
            # 可以添加其他告警通知方式，如WebSocket推送、邮件通知等
            
        except Exception as e:
            logger.error(f"处理告警异常: {e}")
    
    def _save_alarm(self, alarm_data: Dict) -> bool:
        """保存告警到数据库
        
        Args:
            alarm_data: 告警数据
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 转换数据格式
            bbox_json = json.dumps(alarm_data["bbox"])
            created_at = datetime.fromtimestamp(alarm_data["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            
            # 插入数据
            cursor.execute(
                """
                INSERT INTO alarms (
                    alarm_id, task_id, stream_id, label, confidence, 
                    bbox, frame_id, timestamp, created_at, status, level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alarm_data["alarm_id"], alarm_data["task_id"], 
                    alarm_data["stream_id"], alarm_data["label"], 
                    alarm_data["confidence"], bbox_json, alarm_data["frame_id"], 
                    alarm_data["timestamp"], created_at, alarm_data["status"], 
                    alarm_data["level"]
                )
            )
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"保存告警异常: {e}")
            return False
    
    def _save_alarm_image(self, alarm_data: Dict) -> Optional[str]:
        """保存告警图像
        
        Args:
            alarm_data: 告警数据
            
        Returns:
            图像路径
        """
        # TODO: 实现保存告警图像逻辑，需要从任务结果中获取图像数据
        # 示例路径
        image_path = f"temp_frames/{alarm_data['stream_id']}/{alarm_data['task_id']}/{alarm_data['alarm_id']}.jpg"
        
        return image_path
    
    def _update_alarm_image_path(self, alarm_id: str, image_path: str) -> bool:
        """更新告警图像路径
        
        Args:
            alarm_id: 告警ID
            image_path: 图像路径
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE alarms SET image_path = ? WHERE alarm_id = ?",
                (image_path, alarm_id)
            )
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"更新告警图像路径异常: {e}")
            return False
    
    def get_alarms(self, filters: Dict = None) -> List[Dict]:
        """获取告警列表
        
        Args:
            filters: 过滤条件
            
        Returns:
            告警列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建查询
            query = """
                SELECT alarm_id, task_id, stream_id, label, confidence,
                bbox, frame_id, timestamp, created_at, status, level,
                image_path, video_path
                FROM alarms
            """
            
            # 添加过滤条件
            params = []
            where_clauses = []
            
            if filters:
                if "alarm_id" in filters:
                    where_clauses.append("alarm_id = ?")
                    params.append(filters["alarm_id"])
                
                if "task_id" in filters:
                    where_clauses.append("task_id = ?")
                    params.append(filters["task_id"])
                
                if "stream_id" in filters:
                    where_clauses.append("stream_id = ?")
                    params.append(filters["stream_id"])
                
                if "label" in filters:
                    where_clauses.append("label = ?")
                    params.append(filters["label"])
                
                if "status" in filters:
                    where_clauses.append("status = ?")
                    params.append(filters["status"])
                
                if "level" in filters:
                    where_clauses.append("level = ?")
                    params.append(filters["level"])
                
                if "start_time" in filters:
                    where_clauses.append("created_at >= ?")
                    params.append(datetime.fromtimestamp(filters["start_time"]).strftime("%Y-%m-%d %H:%M:%S"))
                
                if "end_time" in filters:
                    where_clauses.append("created_at <= ?")
                    params.append(datetime.fromtimestamp(filters["end_time"]).strftime("%Y-%m-%d %H:%M:%S"))
            
            # 拼接查询条件
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            
            # 添加排序
            query += " ORDER BY created_at DESC"
            
            # 添加分页
            if filters and "limit" in filters:
                query += " LIMIT ?"
                params.append(filters["limit"])
                
                if "offset" in filters:
                    query += " OFFSET ?"
                    params.append(filters["offset"])
            
            # 执行查询
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            # 转换结果
            alarms = []
            for row in rows:
                alarms.append({
                    "alarm_id": row[0],
                    "task_id": row[1],
                    "stream_id": row[2],
                    "label": row[3],
                    "confidence": row[4],
                    "bbox": json.loads(row[5]) if row[5] else [],
                    "frame_id": row[6],
                    "timestamp": row[7],
                    "created_at": row[8],
                    "status": row[9],
                    "level": row[10],
                    "image_path": row[11],
                    "video_path": row[12]
                })
            
            return alarms
            
        except Exception as e:
            logger.error(f"获取告警列表异常: {e}")
            return []
    
    def update_alarm_status(self, alarm_id: str, status: str) -> bool:
        """更新告警状态
        
        Args:
            alarm_id: 告警ID
            status: 状态 ('new', 'processed', 'ignored')
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE alarms SET status = ? WHERE alarm_id = ?",
                (status, alarm_id)
            )
            conn.commit()
            conn.close()
            
            # 发布告警状态更新事件
            self.event_bus.publish(Event(
                "alarm.status_updated",
                "alarm_module",
                {
                    "alarm_id": alarm_id,
                    "status": status
                }
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"更新告警状态异常: {e}")
            return False
    
    def get_alarm_image(self, alarm_id: str) -> Tuple[Optional[str], Optional[str]]:
        """获取告警图像路径
        
        Args:
            alarm_id: 告警ID
            
        Returns:
            (图像路径, 错误消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT image_path FROM alarms WHERE alarm_id = ?",
                (alarm_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return None, "告警不存在"
                
            image_path = result[0]
            if not image_path:
                return None, "图像不存在"
                
            return image_path, None
            
        except Exception as e:
            logger.error(f"获取告警图像路径异常: {e}")
            return None, str(e)
    
    def get_alarm_video(self, alarm_id: str) -> Tuple[Optional[str], Optional[str]]:
        """获取告警视频路径
        
        Args:
            alarm_id: 告警ID
            
        Returns:
            (视频路径, 错误消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT video_path FROM alarms WHERE alarm_id = ?",
                (alarm_id,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return None, "告警不存在"
                
            video_path = result[0]
            if not video_path:
                return None, "视频不存在"
                
            return video_path, None
            
        except Exception as e:
            logger.error(f"获取告警视频路径异常: {e}")
            return None, str(e)
    
    def delete_alarm(self, alarm_id: str) -> bool:
        """删除告警
        
        Args:
            alarm_id: 告警ID
            
        Returns:
            是否成功
        """
        try:
            # 获取告警图像和视频路径
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT image_path, video_path FROM alarms WHERE alarm_id = ?",
                (alarm_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return False
                
            image_path, video_path = result
            
            # 删除告警记录
            cursor.execute(
                "DELETE FROM alarms WHERE alarm_id = ?",
                (alarm_id,)
            )
            conn.commit()
            conn.close()
            
            # TODO: 删除关联的图像和视频文件
            
            # 发布告警删除事件
            self.event_bus.publish(Event(
                "alarm.deleted",
                "alarm_module",
                {"alarm_id": alarm_id}
            ))
            
            return True
            
        except Exception as e:
            logger.error(f"删除告警异常: {e}")
            return False

# 全局告警管理模块实例
def get_alarm_module():
    """获取全局告警管理模块实例"""
    return AlarmModule.get_instance() 