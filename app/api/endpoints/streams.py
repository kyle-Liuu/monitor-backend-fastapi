"""
视频流管理API端点
专注于视频流的完整生命周期管理
- 视频流增删改查
- 视频流启动停止控制
- 视频流状态管理和监控
- RTSP连接测试
- 视频流截图功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import json
import time
import subprocess
import tempfile
import os
from datetime import datetime

from ...schemas.stream import (
    StreamCreate, StreamInfo, StreamUpdate, StreamStats,
    StreamTest, StreamTestResult, StreamSnapshot,
    StreamListResponse, StreamOperationResponse, BaseResponse
)
from ...core.analyzer.stream_module import get_stream_module
from ...utils.utils import success_response, error_response, get_current_active_user, generate_unique_id
from ...db.database import get_db
from ...db.models import VideoStream

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 获取流管理模块
stream_manager = get_stream_module()

# ============================================================================
# 视频流基础CRUD操作
# ============================================================================

@router.post("", response_model=StreamOperationResponse)
def create_stream(
    stream_data: StreamCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """创建新的视频流"""
    try:
        # 生成唯一ID（如果未提供）
        stream_id = stream_data.stream_id or generate_unique_id("stream")
        
        # 检查stream_id是否已存在
        existing = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"视频流ID已存在: {stream_id}")
        
        # 添加到流管理器
        success, error = stream_manager.add_stream(
            stream_id=stream_id,
            url=stream_data.url,
            name=stream_data.name,
            description=stream_data.description,
            stream_type=stream_data.stream_type.value
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=f"创建视频流失败: {error}")
        
        # 保存到数据库
        db_stream = VideoStream(
            stream_id=stream_id,
            name=stream_data.name,
            url=stream_data.url,
            description=stream_data.description,
            stream_type=stream_data.stream_type.value,
            status="inactive"
        )
        
        db.add(db_stream)
        db.commit()
        db.refresh(db_stream)
        
        return StreamOperationResponse(
            success=True,
            stream_id=stream_id,
            operation="create",
            message="视频流创建成功",
            data={"stream_id": stream_id, "name": stream_data.name}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建视频流异常: {e}")
        raise HTTPException(status_code=500, detail=f"创建视频流失败: {str(e)}")


@router.get("", response_model=StreamListResponse)
def list_streams(
    # 兼容前端发送的参数格式
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    skip: Optional[int] = Query(None, ge=0, description="跳过数量（兼容参数）"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="限制数量（兼容参数）"),
    # 过滤参数
    status: Optional[str] = Query(None, description="状态过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    name: Optional[str] = Query(None, description="名称过滤"),
    stream_type: Optional[str] = Query(None, description="流类型过滤"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取视频流列表"""
    try:
        # 处理分页参数兼容性
        if skip is not None and limit is not None:
            # 前端使用skip/limit格式
            actual_page = (skip // limit) + 1 if limit > 0 else 1
            actual_page_size = limit
        else:
            # 使用原始page/page_size格式
            actual_page = page
            actual_page_size = page_size
        
        # 构建查询
        query = db.query(VideoStream)
        
        # 状态过滤
        if status:
            query = query.filter(VideoStream.status == status)
        
        # 流类型过滤
        if stream_type:
            query = query.filter(VideoStream.stream_type == stream_type)
        
        # 名称过滤
        if name:
            query = query.filter(VideoStream.name.like(f"%{name}%"))
        
        # 搜索过滤（通用搜索）
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                VideoStream.name.like(search_pattern) |
                VideoStream.description.like(search_pattern) |
                VideoStream.url.like(search_pattern)
            )
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        streams = query.offset((actual_page - 1) * actual_page_size).limit(actual_page_size).all()
        
        # 获取运行时状态信息
        stream_items = []
        for stream in streams:
            # 从流管理器获取实时状态
            stream_info = stream_manager.get_stream_info(stream.stream_id)
            
            stream_data = {
                "stream_id": stream.stream_id,
                "name": stream.name,
                "url": stream.url,
                "description": stream.description,
                "stream_type": stream.stream_type,
                "status": stream_info.get("status", "inactive") if stream_info else "inactive",
                "frame_width": stream.frame_width,
                "frame_height": stream.frame_height,
                "fps": stream.fps,
                "consumer_count": stream_info.get("consumer_count", 0) if stream_info else 0,
                "last_frame_time": stream_info.get("last_frame_time") if stream_info else stream.last_frame_time,
                "last_online_time": stream.last_online_time,
                "frame_count": stream.frame_count,
                "error_message": stream_info.get("error") if stream_info else stream.error_message,
                "created_at": stream.created_at,
                "updated_at": stream.updated_at
            }
            stream_items.append(StreamInfo(**stream_data))
        
        return StreamListResponse(
            total=total,
            items=stream_items,
            page=actual_page,
            page_size=actual_page_size
        )
        
    except Exception as e:
        logger.error(f"获取视频流列表异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频流列表失败: {str(e)}")


@router.get("/{stream_id}", response_model=StreamInfo)
def get_stream(
    stream_id: str = Path(..., description="视频流ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """获取视频流详情"""
    try:
        # 从数据库获取基础信息
        stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 从流管理器获取实时状态
        stream_info = stream_manager.get_stream_info(stream_id)
        
        return StreamInfo(
            stream_id=stream.stream_id,
            name=stream.name,
            url=stream.url,
            description=stream.description,
            stream_type=stream.stream_type,
            status=stream_info.get("status", "inactive") if stream_info else "inactive",
            frame_width=stream.frame_width,
            frame_height=stream.frame_height,
            fps=stream.fps,
            consumer_count=stream_info.get("consumer_count", 0) if stream_info else 0,
            last_frame_time=stream_info.get("last_frame_time") if stream_info else stream.last_frame_time,
            last_online_time=stream.last_online_time,
            frame_count=stream.frame_count,
            error_message=stream_info.get("error") if stream_info else stream.error_message,
            created_at=stream.created_at,
            updated_at=stream.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频流详情异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频流详情失败: {str(e)}")


@router.put("/{stream_id}", response_model=StreamOperationResponse)
def update_stream(
    stream_data: StreamUpdate,
    stream_id: str = Path(..., description="视频流ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """更新视频流信息"""
    try:
        # 检查视频流是否存在
        stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 更新流管理器
        update_data = {k: v for k, v in stream_data.dict().items() if v is not None}
        success, error = stream_manager.update_stream(stream_id, **update_data)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"更新视频流失败: {error}")
        
        # 更新数据库
        if stream_data.name is not None:
            stream.name = stream_data.name
        if stream_data.url is not None:
            stream.url = stream_data.url
        if stream_data.description is not None:
            stream.description = stream_data.description
        if stream_data.stream_type is not None:
            stream.stream_type = stream_data.stream_type.value
        
        stream.updated_at = datetime.utcnow()
        db.commit()
        
        return StreamOperationResponse(
            success=True,
            stream_id=stream_id,
            operation="update",
            message="视频流更新成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新视频流异常: {e}")
        raise HTTPException(status_code=500, detail=f"更新视频流失败: {str(e)}")


@router.delete("/{stream_id}", response_model=StreamOperationResponse)
def delete_stream(
    stream_id: str = Path(..., description="视频流ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """删除视频流"""
    try:
        # 检查视频流是否存在
        stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 从流管理器删除
        success, error = stream_manager.delete_stream(stream_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"删除视频流失败: {error}")
        
        # 从数据库删除
        db.delete(stream)
        db.commit()
        
        return StreamOperationResponse(
            success=True,
            stream_id=stream_id,
            operation="delete",
            message="视频流删除成功"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除视频流异常: {e}")
        raise HTTPException(status_code=500, detail=f"删除视频流失败: {str(e)}")

# ============================================================================
# 视频流控制操作
# ============================================================================

@router.post("/{stream_id}/start", response_model=StreamOperationResponse)
def start_stream(
    stream_id: str = Path(..., description="视频流ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """启动视频流"""
    try:
        # 检查视频流是否存在
        stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 启动流
        success, error = stream_manager.start_stream(stream_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"启动视频流失败: {error}")
        
        # 更新数据库状态
        stream.status = "active"
        stream.updated_at = datetime.utcnow()
        db.commit()
        
        return StreamOperationResponse(
            success=True,
            stream_id=stream_id,
            operation="start",
            message="视频流启动成功",
            data={"status": "active"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动视频流异常: {e}")
        raise HTTPException(status_code=500, detail=f"启动视频流失败: {str(e)}")


@router.post("/{stream_id}/stop", response_model=StreamOperationResponse)
def stop_stream(
    stream_id: str = Path(..., description="视频流ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """停止视频流"""
    try:
        # 检查视频流是否存在
        stream = db.query(VideoStream).filter(VideoStream.stream_id == stream_id).first()
        if not stream:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 停止流
        success, error = stream_manager.stop_stream(stream_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"停止视频流失败: {error}")
        
        # 更新数据库状态
        stream.status = "inactive"
        stream.updated_at = datetime.utcnow()
        db.commit()
        
        return StreamOperationResponse(
            success=True,
            stream_id=stream_id,
            operation="stop",
            message="视频流停止成功",
            data={"status": "inactive"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"停止视频流异常: {e}")
        raise HTTPException(status_code=500, detail=f"停止视频流失败: {str(e)}")

# ============================================================================
# 视频流监控和诊断
# ============================================================================

@router.get("/{stream_id}/status", response_model=BaseResponse)
def get_stream_status(
    stream_id: str = Path(..., description="视频流ID"),
    current_user = Depends(get_current_active_user)
):
    """获取视频流状态"""
    try:
        stream_info = stream_manager.get_stream_info(stream_id)
        if not stream_info:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        return BaseResponse(
            code=200,
            message="获取流状态成功",
            data=stream_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取流状态异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取流状态失败: {str(e)}")


@router.get("/{stream_id}/stats", response_model=StreamStats)
def get_stream_stats(
    stream_id: str = Path(..., description="视频流ID"),
    current_user = Depends(get_current_active_user)
):
    """获取视频流统计信息"""
    try:
        stream_info = stream_manager.get_stream_info(stream_id)
        if not stream_info:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        # 构建统计信息
        stats = StreamStats(
            stream_id=stream_id,
            fps=stream_info.get("fps"),
            resolution=stream_info.get("resolution"),
            bitrate=stream_info.get("bitrate"),
            frame_count=stream_info.get("frame_count", 0),
            error_count=stream_info.get("error_count", 0),
            last_error=stream_info.get("last_error"),
            uptime_seconds=stream_info.get("uptime_seconds", 0)
        )
        
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取流统计异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取流统计失败: {str(e)}")


@router.post("/test", response_model=StreamTestResult)
def test_stream_connection(
    test_data: StreamTest,
    current_user = Depends(get_current_active_user)
):
    """测试视频流连接"""
    try:
        url = test_data.url
        timeout = test_data.timeout
        
        start_time = time.time()
        
        # 使用ffprobe测试连接
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-rtsp_transport', 'tcp',
            '-analyzeduration', '2000000',
            '-probesize', '2000000',
            '-i', url,
            '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
            '-of', 'json'
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout
            )
            
            response_time = time.time() - start_time
            
            if result.returncode == 0:
                # 解析输出获取视频信息
                output = json.loads(result.stdout)
                streams = output.get('streams', [])
                
                resolution = None
                fps = None
                codec = None
                
                for stream in streams:
                    if stream.get('codec_type') == 'video':
                        width = stream.get('width')
                        height = stream.get('height')
                        if width and height:
                            resolution = f"{width}x{height}"
                        
                        frame_rate = stream.get('r_frame_rate', '0/1')
                        if '/' in frame_rate:
                            num, den = map(int, frame_rate.split('/'))
                            if den > 0:
                                fps = round(num / den, 2)
                        
                        codec = stream.get('codec_name')
                        break
                
                return StreamTestResult(
                    success=True,
                    url=url,
                    response_time=response_time,
                    resolution=resolution,
                    fps=fps,
                    codec=codec
                )
            else:
                error_msg = result.stderr.strip() or "连接失败"
                return StreamTestResult(
                    success=False,
                    url=url,
                    response_time=response_time,
                    error_message=error_msg
                )
                
        except subprocess.TimeoutExpired:
            return StreamTestResult(
                success=False,
                url=url,
                response_time=timeout,
                error_message=f"连接超时({timeout}秒)"
            )
        except FileNotFoundError:
            return StreamTestResult(
                success=False,
                url=url,
                error_message="未找到ffprobe命令，请安装FFmpeg"
            )
            
    except Exception as e:
        logger.error(f"测试流连接异常: {e}")
        return StreamTestResult(
            success=False,
            url=test_data.url,
            error_message=f"测试异常: {str(e)}"
        )


@router.get("/{stream_id}/snapshot", response_model=StreamSnapshot)
def get_stream_snapshot(
    stream_id: str = Path(..., description="视频流ID"),
    current_user = Depends(get_current_active_user)
):
    """获取视频流截图"""
    try:
        # 检查流是否存在和活跃
        stream_info = stream_manager.get_stream_info(stream_id)
        if not stream_info:
            raise HTTPException(status_code=404, detail="视频流不存在")
        
        if stream_info.get("status") != "active":
            raise HTTPException(status_code=400, detail="视频流未启动")
        
        # 生成截图文件路径
        timestamp = datetime.now()
        filename = f"{stream_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
        snapshot_path = os.path.join(tempfile.gettempdir(), filename)
        
        # 使用ffmpeg截图
        url = stream_info.get("url")
        cmd = [
            'ffmpeg',
            '-i', url,
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            snapshot_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        
        if result.returncode == 0 and os.path.exists(snapshot_path):
            # 计算文件大小
            file_size = os.path.getsize(snapshot_path)
            
            # 这里应该将文件保存到合适的位置并返回URL
            # 暂时返回文件路径
            snapshot_url = f"/api/streams/{stream_id}/snapshot/{filename}"
            
            return StreamSnapshot(
                stream_id=stream_id,
                snapshot_url=snapshot_url,
                timestamp=timestamp,
                format="jpeg",
                size=file_size
            )
        else:
            raise HTTPException(status_code=500, detail="截图失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取流截图异常: {e}")
        raise HTTPException(status_code=500, detail=f"获取流截图失败: {str(e)}") 