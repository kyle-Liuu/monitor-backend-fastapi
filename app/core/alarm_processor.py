"""
告警处理服务
- 处理AI检测结果，自动判断是否需要告警
- 自动保存告警相关媒体文件（前后N秒视频+检测图片）
- 发送实时通知
- 记录告警到数据库
"""

import os
import json
import uuid
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

from .video_recorder import video_recorder
from .websocket_manager import websocket_manager
from ..db.database import SessionLocal
from ..db.models import Alarm, Task
from ..utils.utils import generate_unique_id
from ..core.analyzer.utils.id_generator import generate_unique_id as analyzer_generate_id

logger = logging.getLogger(__name__)

class AlarmProcessor:
    """告警处理器"""
    
    def __init__(self):
        self.alarm_base_path = "alarms"
        self.cooldown_cache = {}  # 告警冷却缓存
        
        # 确保告警目录存在
        os.makedirs(self.alarm_base_path, exist_ok=True)
    
    async def process_detection_result(self, task_id: str, detection_result: Dict[str, Any]):
        """
        处理算法检测结果，自动判断并保存告警
        
        Args:
            task_id: 任务ID
            detection_result: 检测结果
                {
                    "task_id": "task_123",
                    "stream_id": "stream_456",
                    "timestamp": datetime,
                    "detections": [
                        {
                            "class": "person",
                            "confidence": 0.95,
                            "bbox": [x1, y1, x2, y2]
                        }
                    ],
                    "original_image": "base64_image_data",
                    "annotated_image": "base64_image_data"
                }
        """
        try:
            # 1. 检查是否满足告警条件
            should_alarm, alarm_reason = await self._should_trigger_alarm(task_id, detection_result)
            
            if not should_alarm:
                logger.debug(f"任务 {task_id} 检测结果不满足告警条件: {alarm_reason}")
                return
            
            # 2. 检查告警冷却时间
            if self._is_in_cooldown(task_id):
                logger.debug(f"任务 {task_id} 在告警冷却期内，跳过此次告警")
                return
            
            # 3. 创建告警记录
            alarm_id = await self._create_alarm_record(task_id, detection_result)
            
            # 4. 自动保存告警媒体文件
            await self._save_alarm_media(alarm_id, detection_result)
            
            # 5. 发送实时通知
            await self._send_alarm_notification(alarm_id, detection_result)
            
            # 6. 设置告警冷却
            await self._set_alarm_cooldown(task_id)
            
            logger.info(f"告警 {alarm_id} 处理完成")
            
        except Exception as e:
            logger.error(f"处理检测结果异常: {e}")
    
    async def _should_trigger_alarm(self, task_id: str, detection_result: Dict) -> tuple[bool, str]:
        """判断是否应该触发告警"""
        try:
            # 获取任务配置
            task_config = await self._get_task_config(task_id)
            alarm_config = task_config.get("alarm_config", {})
            
            if not alarm_config.get("enabled", False):
                return False, "告警功能未启用"
            
            # 检查检测结果
            detections = detection_result.get("detections", [])
            if not detections:
                return False, "无检测结果"
            
            # 检查置信度阈值
            confidence_threshold = alarm_config.get("confidence_threshold", 0.8)
            alarm_conditions = alarm_config.get("conditions", ["person"])
            
            for detection in detections:
                class_name = detection.get("class", "")
                confidence = detection.get("confidence", 0.0)
                
                # 检查是否是告警类别且置信度满足条件
                if class_name in alarm_conditions and confidence >= confidence_threshold:
                    return True, f"检测到 {class_name}，置信度 {confidence:.2f}"
            
            return False, "未满足告警条件（类别或置信度不够）"
            
        except Exception as e:
            logger.error(f"判断告警条件异常: {e}")
            return False, f"判断异常: {str(e)}"
    
    def _is_in_cooldown(self, task_id: str) -> bool:
        """检查是否在告警冷却期内"""
        if task_id not in self.cooldown_cache:
            return False
        
        last_alarm_time = self.cooldown_cache[task_id]
        cooldown_seconds = 30  # 默认30秒冷却时间
        
        return (datetime.now() - last_alarm_time).total_seconds() < cooldown_seconds
    
    async def _set_alarm_cooldown(self, task_id: str):
        """设置告警冷却时间"""
        self.cooldown_cache[task_id] = datetime.now()
    
    async def _create_alarm_record(self, task_id: str, detection_result: Dict) -> str:
        """创建告警记录"""
        try:
            # 生成告警ID
            alarm_id = generate_unique_id("alarm")
            
            # 解析检测结果
            detections = detection_result.get("detections", [])
            main_detection = detections[0] if detections else {}
            
            # 创建告警记录
            db = SessionLocal()
            try:
                alarm = Alarm(
                    alarm_id=alarm_id,
                    task_id=task_id,
                    alarm_type=main_detection.get("class", "unknown"),
                    confidence=main_detection.get("confidence", 0.0),
                    bbox=json.dumps(main_detection.get("bbox", [])),
                    # 使用新的字段格式
                    level="medium",      # 新字段：low, medium, high, critical
                    status="new",        # 新字段：new, processed, ignored
                    # 兼容性字段（保留旧字段以防其他地方还在使用）
                    severity="medium",   # 兼容性字段
                    processed=False,     # 兼容性字段
                    created_at=detection_result.get("timestamp", datetime.now())
                )
                
                db.add(alarm)
                db.commit()
                db.refresh(alarm)
            finally:
                db.close()
            
            logger.info(f"创建告警记录成功: {alarm_id}")
            return alarm_id
            
        except Exception as e:
            logger.error(f"创建告警记录失败: {e}")
            raise
    
    async def _save_alarm_media(self, alarm_id: str, detection_result: Dict):
        """自动保存告警相关媒体文件"""
        try:
            # 创建告警目录
            alarm_dir = Path(self.alarm_base_path) / alarm_id
            alarm_dir.mkdir(parents=True, exist_ok=True)
            
            # 获取任务配置
            task_config = await self._get_task_config(detection_result["task_id"])
            alarm_config = task_config.get("alarm_config", {})
            
            media_paths = {}
            
            # 1. 保存检测图片
            if alarm_config.get("save_images", True):
                image_paths = await self._save_alarm_images(alarm_id, detection_result, alarm_dir)
                media_paths.update(image_paths)
            
            # 2. 保存告警视频片段
            if alarm_config.get("save_video", True):
                video_path = await self._save_alarm_video(alarm_id, detection_result, alarm_config, alarm_dir)
                if video_path:
                    media_paths["video_clip"] = video_path
            
            # 3. 更新数据库中的媒体文件路径
            await self._update_alarm_media_paths(alarm_id, media_paths)
            
            logger.info(f"告警 {alarm_id} 媒体文件保存完成: {media_paths}")
            
        except Exception as e:
            logger.error(f"保存告警媒体文件失败: {e}")
    
    async def _save_alarm_images(self, alarm_id: str, detection_result: Dict, alarm_dir: Path) -> Dict[str, str]:
        """保存告警图片（原图+标注图）"""
        import base64
        
        image_paths = {}
        
        try:
            # 保存原始图片
            original_image_data = detection_result.get("original_image")
            if original_image_data:
                original_path = alarm_dir / "original.jpg"
                with open(original_path, "wb") as f:
                    f.write(base64.b64decode(original_image_data))
                image_paths["original_image"] = str(original_path)
            
            # 保存标注图片
            annotated_image_data = detection_result.get("annotated_image")
            if annotated_image_data:
                annotated_path = alarm_dir / "annotated.jpg"
                with open(annotated_path, "wb") as f:
                    f.write(base64.b64decode(annotated_image_data))
                image_paths["processed_image"] = str(annotated_path)
            
            return image_paths
            
        except Exception as e:
            logger.error(f"保存告警图片失败: {e}")
            return {}
    
    async def _save_alarm_video(self, alarm_id: str, detection_result: Dict, alarm_config: Dict, alarm_dir: Path) -> Optional[str]:
        """保存告警视频片段（前后N秒）"""
        try:
            stream_id = detection_result["stream_id"]
            alarm_time = detection_result["timestamp"]
            pre_seconds = alarm_config.get("pre_seconds", 5)
            post_seconds = alarm_config.get("post_seconds", 5)
            
            # 生成视频文件路径
            video_filename = f"video_{pre_seconds}s_{post_seconds}s.mp4"
            video_path = alarm_dir / video_filename
            
            # 调用视频录制服务保存视频片段
            success = await video_recorder.save_alarm_video_segment(
                stream_id=stream_id,
                alarm_time=alarm_time,
                pre_seconds=pre_seconds,
                post_seconds=post_seconds,
                output_path=str(video_path)
            )
            
            if success:
                logger.info(f"告警视频保存成功: {video_path}")
                return str(video_path)
            else:
                logger.warning(f"告警视频保存失败: {alarm_id}")
                return None
                
        except Exception as e:
            logger.error(f"保存告警视频异常: {e}")
            return None
    
    async def _update_alarm_media_paths(self, alarm_id: str, media_paths: Dict[str, str]):
        """更新数据库中的媒体文件路径"""
        db = SessionLocal()
        try:
            alarm = db.query(Alarm).filter(Alarm.alarm_id == alarm_id).first()
            
            if alarm:
                # 更新媒体文件路径
                alarm.original_image = media_paths.get("original_image")
                alarm.processed_image = media_paths.get("processed_image")
                alarm.video_clip = media_paths.get("video_clip")
                
                db.commit()
                logger.info(f"更新告警 {alarm_id} 媒体文件路径成功")
            
        except Exception as e:
            logger.error(f"更新告警媒体文件路径失败: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _send_alarm_notification(self, alarm_id: str, detection_result: Dict):
        """发送实时告警通知"""
        try:
            # 构造通知消息
            notification = {
                "type": "alarm",
                "alarm_id": alarm_id,
                "task_id": detection_result["task_id"],
                "stream_id": detection_result["stream_id"],
                "timestamp": detection_result["timestamp"].isoformat(),
                "detections": detection_result.get("detections", []),
                "message": f"检测到告警事件: {alarm_id}"
            }
            
            # 通过WebSocket发送通知
            await websocket_manager.broadcast_alarm(notification)
            
            logger.info(f"发送告警通知成功: {alarm_id}")
            
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")
    
    async def _get_task_config(self, task_id: str) -> Dict:
        """获取任务配置"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            
            if task and task.config:
                return json.loads(task.config)
            
            return {}
            
        except Exception as e:
            logger.error(f"获取任务配置失败: {e}")
            return {}
        finally:
            db.close()
    
    def get_alarm_statistics(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """获取告警统计信息"""
        db = SessionLocal()
        try:
            query = db.query(Alarm)
            
            if task_id:
                query = query.filter(Alarm.task_id == task_id)
            
            total_alarms = query.count()
            
            # 统计告警状态（使用新字段，兼容旧字段）
            from sqlalchemy import or_
            unprocessed_alarms = query.filter(
                or_(Alarm.status == "new", Alarm.processed == False)
            ).count()
            processed_alarms = query.filter(
                or_(Alarm.status.in_(["processed", "ignored"]), Alarm.processed == True)
            ).count()
            
            # 按类型统计
            alarm_types = {}
            from sqlalchemy import func
            type_results = query.with_entities(Alarm.alarm_type, func.count(Alarm.alarm_type)).group_by(Alarm.alarm_type).all()
            for alarm_type, count in type_results:
                alarm_types[alarm_type] = count
            
            return {
                "total_alarms": total_alarms,
                "unprocessed_alarms": unprocessed_alarms,
                "processed_alarms": processed_alarms,
                "alarm_types": alarm_types,
                "processing_rate": processed_alarms / total_alarms if total_alarms > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {}
        finally:
            db.close()

# 全局实例
alarm_processor = AlarmProcessor() 