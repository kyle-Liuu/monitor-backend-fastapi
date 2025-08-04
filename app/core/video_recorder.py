"""
RTSP流视频录制管理器
使用FFmpeg实现RTSP流实时录制和报警视频保存
专门用于处理RTSP/RTMP流媒体
"""

import asyncio
import subprocess
import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from collections import deque
import shutil

logger = logging.getLogger(__name__)

class FFmpegVideoRecorder:
    """FFmpeg RTSP流视频录制器
    
    专门用于处理RTSP/RTMP流媒体的实时录制和报警视频保存
    - 支持RTSP/RTMP协议
    - 自动段分割和循环缓冲
    - 报警视频前后N秒保存
    - 按流名称分目录管理
    """
    
    def __init__(self, buffer_seconds: int = 10, fps: int = 25):
        """初始化RTSP流录制器
        
        Args:
            buffer_seconds: 缓冲时长（秒），默认10秒
            fps: 帧率，默认25fps
        """
        self.buffer_seconds = buffer_seconds
        self.fps = fps
        self.recording_streams = {}  # 正在录制的RTSP流
        self.temp_dirs = {}          # 临时目录（按流ID）
        self.segment_lists = {}      # 段列表文件（按流ID）
        
        logger.info(f"初始化RTSP流录制器: 缓冲{buffer_seconds}秒, {fps}fps")
        
    async def start_stream_recording(self, stream_id: str, rtsp_url: str) -> bool:
        """启动RTSP流录制"""
        try:
            # 验证RTSP URL格式
            if not rtsp_url.startswith(('rtsp://', 'rtmp://')):
                logger.error(f"不支持的流协议，仅支持RTSP/RTMP: {rtsp_url}")
                return False
            
            # 创建基础临时目录：backend/tempstream
            base_temp_dir = os.path.join(os.getcwd(), "tempstream")
            os.makedirs(base_temp_dir, exist_ok=True)
            
            # 为每个流创建专门的目录：tempstream/stream_id
            temp_dir = os.path.join(base_temp_dir, stream_id)
            os.makedirs(temp_dir, exist_ok=True)
            
            # 清理旧的段文件（如果存在）
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    if file.startswith('segment_') and file.endswith('.mp4'):
                        try:
                            os.remove(os.path.join(temp_dir, file))
                        except Exception as e:
                            logger.warning(f"清理旧段文件失败 {file}: {e}")
            
            self.temp_dirs[stream_id] = temp_dir
            
            # 创建段列表文件
            segment_list_file = os.path.join(temp_dir, "segments.txt")
            self.segment_lists[stream_id] = segment_list_file
            
            # FFmpeg命令：RTSP流实时录制到临时段文件
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出文件
                '-rtsp_transport', 'tcp',  # 使用TCP传输，更稳定
                '-rtsp_flags', 'prefer_tcp',  # 优先使用TCP
                '-i', rtsp_url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',  # 最快编码速度
                '-tune', 'zerolatency',  # 零延迟调优
                '-g', str(self.fps),  # GOP大小等于帧率
                '-keyint_min', str(self.fps),  # 最小关键帧间隔
                '-f', 'segment',
                '-segment_time', '1',  # 每1秒一个段
                '-segment_format', 'mp4',
                '-reset_timestamps', '1',  # 重置时间戳
                '-segment_list', segment_list_file,
                '-segment_list_flags', 'live',  # 实时更新段列表
                '-segment_list_size', str(self.buffer_seconds + 2),  # 保留的段数量
                '-segment_wrap', str(self.buffer_seconds + 2),  # 循环覆盖
                os.path.join(temp_dir, 'segment_%03d.mp4')
            ]
            
            logger.info(f"启动RTSP流录制命令: {' '.join(ffmpeg_cmd)}")
            logger.info(f"RTSP流地址: {rtsp_url}")
            logger.info(f"段文件保存目录: {temp_dir}")
            
            # 启动FFmpeg进程
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.recording_streams[stream_id] = {
                'process': process,
                'start_time': time.time(),
                'temp_dir': temp_dir,
                'segment_list': segment_list_file,
                'rtsp_url': rtsp_url,
                'stream_type': 'rtsp'
            }
            
            logger.info(f"开始录制RTSP流 {stream_id}，临时目录: {temp_dir}")
            
            # 异步监控FFmpeg输出
            asyncio.create_task(self._monitor_ffmpeg_output(stream_id, process))
            
            return True
            
        except Exception as e:
            logger.error(f"启动RTSP流录制失败 {stream_id}: {e}")
            return False
    
    async def _monitor_ffmpeg_output(self, stream_id: str, process):
        """监控FFmpeg输出"""
        try:
            while True:
                stderr_line = await process.stderr.readline()
                if not stderr_line:
                    break
                    
                line = stderr_line.decode('utf-8', errors='ignore').strip()
                if line:
                    # 记录关键信息
                    if 'Error' in line or 'error' in line:
                        logger.error(f"FFmpeg错误 [{stream_id}]: {line}")
                    elif 'Connection' in line or 'Opening' in line:
                        logger.info(f"FFmpeg连接 [{stream_id}]: {line}")
                    elif 'segment' in line.lower():
                        logger.debug(f"FFmpeg段信息 [{stream_id}]: {line}")
                        
        except Exception as e:
            logger.error(f"监控FFmpeg输出失败 [{stream_id}]: {e}")
    
    async def stop_stream_recording(self, stream_id: str) -> bool:
        """停止RTSP流录制"""
        try:
            if stream_id in self.recording_streams:
                process_info = self.recording_streams[stream_id]
                process = process_info['process']
                rtsp_url = process_info.get('rtsp_url', '')
                
                logger.info(f"正在停止RTSP流录制: {stream_id} ({rtsp_url})")
                
                # 终止FFmpeg进程
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
                
                # 清理段文件，但保留目录结构
                temp_dir = process_info['temp_dir']
                if os.path.exists(temp_dir):
                    try:
                        # 只删除段文件和列表文件，不删除目录
                        for file in os.listdir(temp_dir):
                            if (file.startswith('segment_') and file.endswith('.mp4')) or \
                               file == 'segments.txt' or file == 'segments.txt.tmp':
                                file_path = os.path.join(temp_dir, file)
                                try:
                                    os.remove(file_path)
                                    logger.debug(f"删除RTSP流段文件: {file_path}")
                                except Exception as e:
                                    logger.warning(f"删除段文件失败 {file_path}: {e}")
                    except Exception as e:
                        logger.warning(f"清理RTSP流段文件失败: {e}")
                
                del self.recording_streams[stream_id]
                if stream_id in self.temp_dirs:
                    del self.temp_dirs[stream_id]
                if stream_id in self.segment_lists:
                    del self.segment_lists[stream_id]
                
                logger.info(f"停止录制RTSP流 {stream_id}，已清理段文件")
                return True
                
        except Exception as e:
            logger.error(f"停止RTSP流录制失败 {stream_id}: {e}")
            return False
    
    async def save_alarm_video(self, stream_id: str, alarm_id: str, 
                             pre_seconds: int = 1, post_seconds: int = 1) -> Optional[str]:
        """保存RTSP流报警视频（前后N秒）"""
        try:
            if stream_id not in self.recording_streams:
                logger.error(f"RTSP流 {stream_id} 未在录制中")
                return None
            
            process_info = self.recording_streams[stream_id]
            segment_list_file = process_info['segment_list']
            temp_dir = process_info['temp_dir']
            rtsp_url = process_info.get('rtsp_url', '')
            
            logger.info(f"开始保存RTSP流报警视频: {stream_id} ({rtsp_url})")
            
            # 等待段文件生成
            max_wait_seconds = 10
            wait_count = 0
            while wait_count < max_wait_seconds:
                segments = self.get_available_segments(stream_id)
                if segments:
                    break
                logger.info(f"等待RTSP流段文件生成... ({wait_count}/{max_wait_seconds})")
                await asyncio.sleep(1)
                wait_count += 1
            
            # 使用get_available_segments获取的段文件（已经过路径处理和存在性检查）
            valid_segments = segments
            logger.info(f"获取到RTSP流有效段文件: {len(valid_segments)} 个")
            
            if not valid_segments:
                logger.error("没有可用的RTSP流视频段")
                return None
            
            # 计算需要的段数
            segments_needed = pre_seconds + post_seconds
            if len(valid_segments) < segments_needed:
                logger.warning(f"RTSP流段数不足，需要{segments_needed}个，实际{len(valid_segments)}个")
                segments_needed = len(valid_segments)
            
            # 获取最近的段
            recent_segments = valid_segments[-segments_needed:]
            logger.info(f"使用的RTSP流视频段: {recent_segments}")
            
            # 创建报警视频目录
            alarm_dir = os.path.join("alarms", datetime.now().strftime("%Y%m%d"))
            os.makedirs(alarm_dir, exist_ok=True)
            
            # 生成报警视频文件名，标注为RTSP流
            alarm_video_path = os.path.join(
                alarm_dir, 
                f"{alarm_id}_{datetime.now().strftime('%H%M%S')}.mp4"
            )
            
            # 合并视频段
            if len(recent_segments) == 1:
                # 只有一个段，直接复制
                shutil.copy2(recent_segments[0], alarm_video_path)
                logger.info(f"直接复制单个RTSP流视频段: {recent_segments[0]} -> {alarm_video_path}")
            else:
                # 多个段，需要合并
                concat_file = os.path.join(temp_dir, "concat.txt")
                with open(concat_file, 'w', encoding='utf-8') as f:
                    for segment in recent_segments:
                        # 使用绝对路径并转换Windows路径格式
                        abs_path = os.path.abspath(segment).replace('\\', '/')
                        f.write(f"file '{abs_path}'\n")
                
                logger.info(f"创建RTSP流合并文件: {concat_file}")
                with open(concat_file, 'r') as f:
                    logger.info(f"合并文件内容:\n{f.read()}")
                
                # 使用FFmpeg合并
                concat_cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', concat_file,
                    '-c', 'copy',  # 直接复制，不重新编码
                    '-y',  # 覆盖输出文件
                    alarm_video_path
                ]
                
                logger.info(f"执行RTSP流合并命令: {' '.join(concat_cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *concat_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.error(f"合并RTSP流视频段失败: {stderr.decode()}")
                    return None
                
                # 清理临时文件
                os.remove(concat_file)
            
            logger.info(f"RTSP流报警视频保存成功: {alarm_video_path}")
            return alarm_video_path
            
        except Exception as e:
            logger.error(f"保存RTSP流报警视频失败 {stream_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def save_alarm_video_segment(self, stream_id: str, alarm_time: datetime, 
                                     pre_seconds: int = 5, post_seconds: int = 5,
                                     output_path: str = None) -> bool:
        """
        保存告警视频片段（从循环缓冲区提取指定时间段）
        
        Args:
            stream_id: 视频流ID
            alarm_time: 告警发生时间
            pre_seconds: 告警前保存秒数
            post_seconds: 告警后保存秒数
            output_path: 输出文件路径
        
        Returns:
            bool: 是否保存成功
        """
        try:
            if stream_id not in self.recording_streams:
                logger.error(f"流 {stream_id} 未在录制中，无法保存告警视频")
                return False
            
            # 如果没有指定输出路径，生成默认路径
            if not output_path:
                alarm_id = f"alarm_{int(alarm_time.timestamp())}"
                alarm_dir = f"alarms/{alarm_time.strftime('%Y%m%d')}"
                os.makedirs(alarm_dir, exist_ok=True)
                output_path = f"{alarm_dir}/{alarm_id}_video_{pre_seconds}s_{post_seconds}s.mp4"
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            process_info = self.recording_streams[stream_id]
            temp_dir = process_info['temp_dir']
            
            # 计算需要提取的时间段
            start_time = alarm_time - timedelta(seconds=pre_seconds)
            end_time = alarm_time + timedelta(seconds=post_seconds)
            
            logger.info(f"保存告警视频片段: {stream_id}, 时间段: {start_time} - {end_time}")
            
            # 获取可用的视频段
            available_segments = self.get_available_segments(stream_id)
            
            if not available_segments:
                logger.error(f"流 {stream_id} 没有可用的视频段")
                return False
            
            # 根据时间需求计算需要的段数
            total_duration = pre_seconds + post_seconds
            segments_needed = min(total_duration, len(available_segments))
            
            # 选择最近的视频段
            selected_segments = available_segments[-segments_needed:]
            
            logger.info(f"选择 {len(selected_segments)} 个视频段进行合并")
            
            # 合并视频段
            success = await self._merge_video_segments(selected_segments, output_path)
            
            if success:
                logger.info(f"告警视频保存成功: {output_path}")
                return True
            else:
                logger.error(f"告警视频保存失败: {output_path}")
                return False
                
        except Exception as e:
            logger.error(f"保存告警视频片段异常: {e}")
            return False
    
    async def _merge_video_segments(self, segments: List[str], output_path: str) -> bool:
        """合并视频段"""
        try:
            if len(segments) == 1:
                # 单个段直接复制
                shutil.copy2(segments[0], output_path)
                return True
            
            # 多个段需要合并
            # 创建临时文件列表
            temp_list_file = f"{output_path}.txt"
            
            with open(temp_list_file, 'w') as f:
                for segment in segments:
                    f.write(f"file '{os.path.abspath(segment)}'\n")
            
            # 使用FFmpeg合并
            ffmpeg_cmd = [
                'ffmpeg', '-f', 'concat', '-safe', '0',
                '-i', temp_list_file,
                '-c', 'copy',
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            logger.debug(f"FFmpeg合并命令: {' '.join(ffmpeg_cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # 清理临时文件
            try:
                os.remove(temp_list_file)
            except:
                pass
            
            if process.returncode == 0:
                logger.info(f"视频段合并成功: {output_path}")
                return True
            else:
                logger.error(f"视频段合并失败: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"合并视频段异常: {e}")
            return False
    
    def get_recording_status(self, stream_id: str) -> Dict:
        """获取RTSP流录制状态"""
        if stream_id not in self.recording_streams:
            return {"status": "not_recording", "message": "RTSP流未在录制中"}
        
        process_info = self.recording_streams[stream_id]
        process = process_info['process']
        rtsp_url = process_info.get('rtsp_url', '')
        
        status = {
            "status": "recording" if process.returncode is None else "stopped",
            "stream_type": "rtsp",
            "rtsp_url": rtsp_url,
            "start_time": process_info['start_time'],
            "temp_dir": process_info['temp_dir'],
            "process_pid": process.pid,
            "returncode": process.returncode
        }
        
        # 检查进程是否还在运行
        if process.returncode is not None:
            status["status"] = "stopped"
            status["stop_reason"] = f"RTSP流录制进程退出，代码: {process.returncode}"
        
        return status
    
    def get_available_segments(self, stream_id: str) -> List[str]:
        """获取可用的视频段"""
        try:
            if stream_id not in self.segment_lists:
                logger.debug(f"流 {stream_id} 不在段列表中")
                return []
            
            segment_list_file = self.segment_lists[stream_id]
            temp_dir = self.temp_dirs.get(stream_id, "")
            
            logger.debug(f"尝试获取段列表 [{stream_id}]")
            logger.debug(f"段列表文件: {segment_list_file}")
            logger.debug(f"临时目录: {temp_dir}")
            
            # 尝试读取主文件，如果不存在或为空，尝试读取临时文件
            files_to_try = [segment_list_file, segment_list_file + '.tmp']
            
            for file_path in files_to_try:
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                        
                        logger.debug(f"读取文件 {file_path}, 内容长度: {len(content)}")
                        
                        if content:
                            segments = content.split('\n')
                            # 过滤存在的文件
                            valid_segments = []
                            for s in segments:
                                if s and s.strip():
                                    s = s.strip()
                                    # 处理相对路径 - 如果是相对路径，需要加上temp_dir
                                    if not os.path.isabs(s) and temp_dir:
                                        full_path = os.path.join(temp_dir, s)
                                        logger.debug(f"转换相对路径: {s} -> {full_path}")
                                    else:
                                        full_path = s
                                        
                                    if os.path.exists(full_path):
                                        valid_segments.append(full_path)
                                        logger.debug(f"段文件存在: {full_path}")
                                    else:
                                        logger.debug(f"段文件不存在: {full_path}")
                            
                            if valid_segments:
                                logger.debug(f"从段列表文件获取到 {len(valid_segments)} 个有效段")
                                return valid_segments
                        else:
                            logger.debug(f"段列表文件为空: {file_path}")
                            
                    except Exception as e:
                        logger.debug(f"读取段列表文件失败 {file_path}: {e}")
                        continue
                else:
                    logger.debug(f"段列表文件不存在: {file_path}")
            
            # 备用方案：直接扫描目录中的段文件
            logger.debug("段列表文件读取失败，尝试直接扫描目录")
            if temp_dir and os.path.exists(temp_dir):
                segment_files = []
                try:
                    for filename in os.listdir(temp_dir):
                        if filename.startswith('segment_') and filename.endswith('.mp4'):
                            file_path = os.path.join(temp_dir, filename)
                            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                                segment_files.append(file_path)
                    
                    if segment_files:
                        # 按文件名排序
                        segment_files.sort()
                        logger.debug(f"从目录扫描获取到 {len(segment_files)} 个段文件")
                        return segment_files
                    else:
                        logger.debug("目录中没有找到有效的段文件")
                except Exception as e:
                    logger.debug(f"扫描目录失败: {e}")
            else:
                logger.debug(f"临时目录不存在或为空: {temp_dir}")
                        
            return []
            
        except Exception as e:
            logger.error(f"获取视频段失败 {stream_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

# 全局RTSP流录制器实例
video_recorder = FFmpegVideoRecorder() 