"""
AI分析器API端点 - 专注AI分析业务
- 系统控制：分析器启动/停止/状态
- 任务管理：AI分析任务的创建和管理
- 告警管理：告警查询和处理
- 输出管理：分析结果输出配置

注意：视频流管理已移至独立的 streams.py 模块
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import json
import uuid
from datetime import datetime

from ...schemas.analyzer import (
    BaseResponse,
    StreamCreate, StreamInfo, StreamUpdate,
    TaskCreate, TaskInfo, TaskUpdate,
    AlarmInfo, AlarmUpdate, OutputCreate, OutputInfo,
    AnalyzerStatus
)
from ...core.analyzer.analyzer_service import get_analyzer_service
from ...utils.utils import success_response, error_response, get_current_active_user, generate_unique_id as utils_generate_id
from ...db.database import get_db
from ...db.models import Task, VideoStream, Algorithm, Alarm
from ...schemas.task import TaskCreate as TaskCreateModel, TaskResponse
from ...schemas.alarm import AlarmCreate, AlarmResponse

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 获取服务实例
analyzer_service = get_analyzer_service()

# ============================================================================
# 系统控制接口
# ============================================================================

@router.post("/start", response_model=BaseResponse)
async def start_analyzer():
    """启动分析器服务"""
    try:
        success = analyzer_service.start()
        if success:
            return success_response("分析器启动成功")
        else:
            return error_response("分析器启动失败")
    except Exception as e:
        logger.error(f"启动分析器异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop", response_model=BaseResponse)
async def stop_analyzer():
    """停止分析器服务"""
    try:
        success = analyzer_service.stop()
        if success:
            return success_response("分析器停止成功")
        else:
            return error_response("分析器停止失败")
    except Exception as e:
        logger.error(f"停止分析器异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=BaseResponse)
async def get_analyzer_status():
    """获取分析器状态"""
    try:
        status = analyzer_service.get_status()
        return success_response("获取状态成功", status)
    except Exception as e:
        logger.error(f"获取分析器状态异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# 任务管理接口 (集成自 tasks.py)
# ============================================================================

@router.post("/tasks", response_model=TaskResponse)
def create_task(
    task: TaskCreateModel, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """创建新的视频分析任务"""
    # 检查流和算法是否存在
    stream = db.query(VideoStream).filter(VideoStream.stream_id == task.stream_id).first()
    algorithm = db.query(Algorithm).filter(Algorithm.algo_id == task.algorithm_id).first()
    
    if not stream:
        raise HTTPException(status_code=404, detail="视频流不存在")
    
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    
    # 生成任务ID
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    # 解析算法配置
    algo_config = json.loads(algorithm.config) if algorithm.config else {}
    
    # 构建任务配置
    task_config = {
        "task_id": task_id,
        "stream_id": stream.stream_id,
        "stream_url": stream.url,
        "algo_id": algorithm.algo_id,
        "algo_package": algorithm.package_name,
        "model_name": algo_config.get("name", "yolov8n"),
        "model_config": algo_config,
        "enable_output": getattr(task, 'enable_output', True),
        "output_url": getattr(task, 'output_url', f"rtmp://localhost/live/{stream.stream_id}_{algorithm.algo_id}"),
        # 告警配置
        "alarm_config": {
            "enabled": True,
            "pre_seconds": 5,
            "post_seconds": 5,
            "save_video": True,
            "save_images": True,
            "confidence_threshold": 0.8
        }
    }
    
    # 使用视频分析器服务创建任务
    success, message, created_task_id = analyzer_service.create_task_with_process_manager(task_config)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    # 保存任务到数据库
    db_task = Task(
        task_id=task_id,
        name=task.name,
        description=task.description or "",
        stream_id=stream.stream_id,
        algorithm_id=algorithm.algo_id,
        status="active",
        config=json.dumps(task_config)
    )
    
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    
    return db_task

@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(
    db: Session = Depends(get_db), 
    status: Optional[str] = None,
    current_user = Depends(get_current_active_user)
):
    """获取任务列表"""
    query = db.query(Task)
    
    if status:
        query = query.filter(Task.status == status)
    
    tasks = query.all()
    
    # 补充任务运行状态
    for task in tasks:
        try:
            runtime_status = analyzer_service.get_task_status(task.task_id)
            if "error" not in runtime_status:
                task.runtime_status = runtime_status
        except:
            pass
    
    return tasks

@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取任务详情"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 补充任务运行状态
    try:
        runtime_status = analyzer_service.get_task_status(task_id)
        if "error" not in runtime_status:
            task.runtime_status = runtime_status
    except:
        pass
    
    return task

@router.delete("/tasks/{task_id}", response_model=dict)
def delete_task(
    task_id: str, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """停止并删除任务"""
    # 获取任务
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 停止任务
    success, message = analyzer_service.stop_task_with_process_manager(task_id)
    
    # 更新数据库
    task.status = "inactive"
    db.commit()
    
    return {"success": success, "message": message, "task_id": task_id}

@router.post("/tasks/{task_id}/start", response_model=dict)
def start_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """启动任务"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 使用分析器服务启动任务
    success, message = analyzer_service.start_task_with_process_manager(
        json.loads(task.config) if task.config else {}
    )
    
    if success:
        # 更新数据库中的任务状态
        task.status = "active"
        db.commit()
        return {"success": True, "message": "任务启动成功", "task_id": task_id}
    else:
        raise HTTPException(status_code=500, detail=f"启动任务失败: {message}")

@router.post("/tasks/{task_id}/stop", response_model=dict)
def stop_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """停止任务"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 使用分析器服务停止任务
    success, message = analyzer_service.stop_task_with_process_manager(task_id)
    
    if success:
        # 更新数据库中的任务状态
        task.status = "inactive"
        db.commit()
        return {"success": True, "message": "任务停止成功", "task_id": task_id}
    else:
        raise HTTPException(status_code=500, detail=f"停止任务失败: {message}")

@router.post("/tasks/batch", response_model=dict)
def batch_operate_tasks(
    data: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """批量操作任务"""
    task_ids = data.get("task_ids", [])
    operation = data.get("operation")
    
    if not task_ids or not operation:
        raise HTTPException(status_code=400, detail="缺少必要参数")
    
    if operation not in ["start", "stop", "delete"]:
        raise HTTPException(status_code=400, detail="不支持的操作类型")
    
    results = []
    for task_id in task_ids:
        try:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                results.append({
                    "task_id": task_id,
                    "success": False,
                    "message": "任务不存在"
                })
                continue
                
            if operation == "start":
                config = json.loads(task.config) if task.config else {}
                success, message = analyzer_service.start_task_with_process_manager(config)
                if success:
                    task.status = "active"
            elif operation == "stop":
                success, message = analyzer_service.stop_task_with_process_manager(task_id)
                if success:
                    task.status = "inactive"
            elif operation == "delete":
                success, message = analyzer_service.stop_task_with_process_manager(task_id)
                if success:
                    db.delete(task)
            
            results.append({
                "task_id": task_id,
                "success": success,
                "message": message or f"{operation}操作成功"
            })
        except Exception as e:
            results.append({
                "task_id": task_id,
                "success": False,
                "message": str(e)
            })
    
    db.commit()
    return {"results": results}

@router.put("/tasks/{task_id}/alarm_config", response_model=Dict)
def update_task_alarm_config(
    task_id: str,
    alarm_config: Dict = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """更新任务的告警配置"""
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新配置
    config = json.loads(task.config) if task.config else {}
    config["alarm_config"] = alarm_config
    task.config = json.dumps(config)
    
    db.commit()
    
    return {
        "code": 200,
        "data": {"task_id": task_id, "alarm_config": alarm_config},
        "msg": "告警配置更新成功"
    }

# ============================================================================
# 系统管理接口
# ============================================================================

@router.get("/system/status", response_model=Dict[str, Any])
def get_system_status(current_user = Depends(get_current_active_user)):
    """获取系统状态"""
    try:
        status = analyzer_service.get_status()
        return {
            "service_status": "running" if analyzer_service.running else "stopped",
            "active_tasks": status.get("active_tasks", 0),
            "total_tasks": status.get("total_tasks", 0),
            "cpu_usage": status.get("cpu_usage", 0),
            "memory_usage": status.get("memory_usage", 0),
            "gpu_usage": status.get("gpu_usage"),
            "active_streams": status.get("active_streams", 0),
            "active_algorithms": status.get("active_algorithms", 0)
        }
    except Exception as e:
        logger.error(f"获取系统状态异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system/performance", response_model=Dict[str, Any])
def get_performance_stats(
    time_range: str = Query("1h", description="时间范围"),
    task_id: Optional[str] = Query(None, description="任务ID"),
    current_user = Depends(get_current_active_user)
):
    """获取性能统计"""
    try:
        # 这里返回模拟数据，实际实现需要从监控系统获取
        import time
        current_time = time.time()
        
        # 生成时间序列数据
        time_points = []
        for i in range(10):
            timestamp = current_time - (10 - i) * 60  # 每分钟一个点
            time_points.append(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)))
        
        return {
            "cpu_usage": [{"timestamp": t, "value": 30 + i * 5} for i, t in enumerate(time_points)],
            "memory_usage": [{"timestamp": t, "value": 40 + i * 3} for i, t in enumerate(time_points)],
            "gpu_usage": [{"timestamp": t, "value": 20 + i * 4} for i, t in enumerate(time_points)],
            "fps_stats": [{"timestamp": t, "fps": 25 + i} for i, t in enumerate(time_points)],
            "error_counts": [{"timestamp": t, "errors": i} for i, t in enumerate(time_points)]
        }
    except Exception as e:
        logger.error(f"获取性能统计异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/restart", response_model=dict)
def restart_system(current_user = Depends(get_current_active_user)):
    """重启系统"""
    try:
        # 先停止再启动
        analyzer_service.stop()
        success = analyzer_service.start()
        if success:
            return {"success": True, "message": "系统重启成功"}
        else:
            raise HTTPException(status_code=500, detail="系统重启失败")
    except Exception as e:
        logger.error(f"重启系统异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# 告警管理接口 (集成自 alarms.py 基础功能)
# ============================================================================

@router.get("/alarms", response_model=Dict[str, Any])
async def get_alarm_list(
    task_id: Optional[str] = Query(None, description="任务ID"),
    stream_id: Optional[str] = Query(None, description="流ID"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取报警列表"""
    try:
        # 构建查询
        query = db.query(Alarm)
        
        if task_id:
            query = query.filter(Alarm.task_id == task_id)
        if stream_id:
            query = query.join(Task).filter(Task.stream_id == stream_id)
        if status:
            query = query.filter(Alarm.processed == (status == "processed"))
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        alarms = query.order_by(Alarm.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        # 构造响应数据
        alarm_list = []
        for alarm in alarms:
            alarm_list.append({
                "alarm_id": alarm.alarm_id,
                "task_id": alarm.task_id,
                "alarm_type": alarm.alarm_type,
                "confidence": alarm.confidence,
                "severity": alarm.severity,
                "processed": alarm.processed,
                "created_at": alarm.created_at.isoformat() if alarm.created_at else None,
                "media_files": {
                    "original_image": alarm.original_image,
                    "processed_image": alarm.processed_image,
                    "video_clip": alarm.video_clip
                }
            })
        
        return {
            "code": 200,
            "data": {
                "alarms": alarm_list,
                "total": total,
                "page": page,
                "page_size": page_size
            },
            "msg": "获取报警列表成功"
        }
        
    except Exception as e:
        logger.error(f"获取报警列表异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取报警列表失败: {str(e)}")

@router.get("/alarms/{alarm_id}", response_model=Dict[str, Any])
async def get_alarm_detail(
    alarm_id: str = Path(..., description="报警ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取报警详情"""
    try:
        alarm = db.query(Alarm).filter(Alarm.alarm_id == alarm_id).first()
        
        if not alarm:
            raise HTTPException(status_code=404, detail="报警不存在")
        
        return {
            "code": 200,
            "data": {
                "alarm_id": alarm.alarm_id,
                "task_id": alarm.task_id,
                "alarm_type": alarm.alarm_type,
                "confidence": alarm.confidence,
                "bbox": alarm.bbox,
                "severity": alarm.severity,
                "processed": alarm.processed,
                "created_at": alarm.created_at.isoformat() if alarm.created_at else None,
                "media_files": {
                    "original_image": alarm.original_image,
                    "processed_image": alarm.processed_image,
                    "video_clip": alarm.video_clip
                }
            },
            "msg": "获取报警详情成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取报警详情异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取报警详情失败: {str(e)}")

@router.put("/alarms/{alarm_id}/process", response_model=Dict[str, Any])
async def process_alarm(
    alarm_id: str = Path(..., description="报警ID"),
    process_data: Dict = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """处理报警"""
    try:
        alarm = db.query(Alarm).filter(Alarm.alarm_id == alarm_id).first()
        
        if not alarm:
            raise HTTPException(status_code=404, detail="报警不存在")
        
        # 更新报警状态
        alarm.processed = True
        alarm.severity = process_data.get("severity", alarm.severity)
        
        db.commit()
        
        return {
            "code": 200,
            "data": {"alarm_id": alarm_id, "processed": True},
            "msg": "报警处理成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理报警异常: {e}")
        raise HTTPException(status_code=500, detail=f"处理报警失败: {str(e)}")

@router.get("/alarms/{alarm_id}/media", response_model=Dict[str, Any])
async def get_alarm_media(
    alarm_id: str = Path(..., description="报警ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取告警媒体文件信息"""
    try:
        alarm = db.query(Alarm).filter(Alarm.alarm_id == alarm_id).first()
        
        if not alarm:
            raise HTTPException(status_code=404, detail="报警不存在")
        
        return {
            "code": 200,
            "data": {
                "alarm_id": alarm_id,
                "media_files": {
                    "original_image": alarm.original_image,
                    "processed_image": alarm.processed_image,
                    "video_clip": alarm.video_clip
                },
                "download_urls": {
                    "original_image": f"/api/analyzer/alarms/{alarm_id}/download/original_image",
                    "processed_image": f"/api/analyzer/alarms/{alarm_id}/download/processed_image",
                    "video_clip": f"/api/analyzer/alarms/{alarm_id}/download/video_clip"
                }
            },
            "msg": "获取告警媒体文件成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取告警媒体文件异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取告警媒体文件失败: {str(e)}")

# ============================================================================
# 输出管理接口 (保持原有功能)
# ============================================================================

@router.post("/outputs", response_model=BaseResponse)
async def create_output(output: OutputCreate):
    """创建输出"""
    try:
        success, error, output_id = analyzer_service.create_output(
            task_id=output.task_id,
            output_type=output.output_type,
            url=output.url,
            config=output.config
        )
        
        if success:
            output_info = analyzer_service.get_output_info(output_id)
            return success_response("输出创建成功", output_info)
        else:
            return error_response(f"输出创建失败: {error}")
    except Exception as e:
        logger.error(f"创建输出异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/outputs", response_model=BaseResponse)
async def list_outputs(task_id: Optional[str] = Query(None, description="任务ID")):
    """获取输出列表"""
    try:
        outputs_info = analyzer_service.get_output_info(task_id=task_id)
        return success_response("获取输出列表成功", outputs_info)
    except Exception as e:
        logger.error(f"获取输出列表异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/outputs/{output_id}", response_model=BaseResponse)
async def delete_output(output_id: str = Path(..., description="输出ID")):
    """删除输出"""
    try:
        success, error = analyzer_service.delete_output(output_id)
        if success:
            return success_response("输出删除成功")
        else:
            return error_response(f"输出删除失败: {error}")
    except Exception as e:
        logger.error(f"删除输出异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/outputs/{output_id}/enable", response_model=BaseResponse)
async def enable_output(output_id: str = Path(..., description="输出ID")):
    """启用输出"""
    try:
        success, error = analyzer_service.enable_output(output_id)
        if success:
            return success_response("输出启用成功")
        else:
            return error_response(f"输出启用失败: {error}")
    except Exception as e:
        logger.error(f"启用输出异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/outputs/{output_id}/disable", response_model=BaseResponse)
async def disable_output(output_id: str = Path(..., description="输出ID")):
    """禁用输出"""
    try:
        success, error = analyzer_service.disable_output(output_id)
        if success:
            return success_response("输出禁用成功")
        else:
            return error_response(f"输出禁用失败: {error}")
    except Exception as e:
        logger.error(f"禁用输出异常: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 