"""
分析器核心进程模块
- 拉流进程（stream_process）：断线重连、流复用、参数自适应
- 算法进程（algorithm_process）：模型池、异常保护、队列溢出保护
- 推流进程（streaming_process）：多协议、健康监控、自动重启
- 告警进程（alarm_process）：双图推送、队列溢出保护
- 所有进程日志、异常、状态共享接口风格统一
- 辅助函数集中管理
"""

import multiprocessing as mp
import cv2
import time
import logging
import json
import os
import subprocess
import signal
import uuid
import numpy as np
from datetime import datetime
import base64
import threading
import json
import traceback
import time
import yaml
from multiprocessing import shared_memory
from typing import Any, Dict, Optional, Tuple, Callable, List

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)

class GlobalConfig:
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        self.config = {}
        self.config_path = os.path.join(os.path.dirname(__file__), '../config.yaml')
        self.load_config()
    
    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = GlobalConfig()
            return cls._instance
    
    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}
    
    def reload_config(self):
        self.load_config()
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def get_section(self, section):
        return self.config.get(section, {})

# 用法示例：
# cfg = GlobalConfig.instance()
# stream_params = cfg.get_section('stream')
# model_params = cfg.get_section('model')
# 推流参数 = cfg.get_section('ffmpeg')

def log_exception(process_type: str, task_id: str, exc: Exception, extra: Optional[Dict[str, Any]] = None) -> None:
    log_data = {
        "level": "ERROR",
        "process_type": process_type,
        "task_id": task_id,
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    if extra:
        log_data.update(extra)
    logger.error(json.dumps(log_data, ensure_ascii=False))

def run_inference(model: Any, frame: Any) -> Tuple[Optional[Any], List[Any]]:
    """
    独立推理函数，返回原始和标准化结果。
    Args:
        model: 推理模型实例
        frame: 输入帧
    Returns:
        (原始结果, 标准化结果列表)
    """
    try:
        return model.infer(frame)
    except Exception as e:
        log_exception("inference", "-", e)
        return None, []

def run_postprocess(postprocessor, infer_result):
    """独立后处理函数，返回后处理结果"""
    try:
        return postprocessor.process({'default': {'engine_result': infer_result, 'model_conf': {}}})
    except Exception as e:
        log_exception("postprocess", "-", e)
        return {}

def report_resource_usage(process_type: str, task_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
    if not psutil:
        logger.warning("psutil未安装，无法采集资源监控数据")
        return
    p = psutil.Process()
    usage = {
        "level": "INFO",
        "type": "resource_usage",
        "process_type": process_type,
        "task_id": task_id,
        "pid": p.pid,
        "cpu_percent": p.cpu_percent(interval=0.1),
        "memory_mb": p.memory_info().rss / 1024 / 1024,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    if extra:
        usage.update(extra)
    logger.info(json.dumps(usage, ensure_ascii=False))

def send_heartbeat(process_type: str, task_id: str) -> None:
    logger.info(json.dumps({
        "level": "INFO",
        "type": "heartbeat",
        "process_type": process_type,
        "task_id": task_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }, ensure_ascii=False))

import uuid

def log_structured(level: str, msg: str, trace_id: Optional[str] = None, task_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    log_data = {
        "level": level,
        "msg": msg,
        "trace_id": trace_id,
        "task_id": task_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    }
    if extra:
        log_data.update(extra)
    if level == "DEBUG":
        logger.debug(json.dumps(log_data, ensure_ascii=False))
    elif level == "INFO":
        logger.info(json.dumps(log_data, ensure_ascii=False))
    elif level == "WARNING":
        logger.warning(json.dumps(log_data, ensure_ascii=False))
    elif level == "ERROR":
        logger.error(json.dumps(log_data, ensure_ascii=False))
    elif level == "CRITICAL":
        logger.critical(json.dumps(log_data, ensure_ascii=False))
    else:
        logger.info(json.dumps(log_data, ensure_ascii=False))

# 用法示例：
# trace_id = str(uuid.uuid4())
# log_structured("INFO", "进程启动", trace_id, task_id)
# log_structured("ERROR", "推理异常", trace_id, task_id, extra={"exception": str(e)})

# 1. 拉流进程
def stream_process(stream_id: str, stream_url: str, ipc_manager, stop_event) -> None:
    """
    拉流进程，负责从流地址拉取视频帧并放入共享队列。
    Args:
        stream_id: 流ID
        stream_url: 流地址
        ipc_manager: IPC管理器实例
        stop_event: 停止事件
    """
    try:
        # 设置进程名
        mp.current_process().name = f"Stream-{stream_id}"
        
        logger.info(f"启动拉流进程: {stream_id}, URL: {stream_url}")
        
        # 获取队列
        frame_queue = ipc_manager.create_stream_queue(stream_id)
        
        # 获取流状态
        stream_status = ipc_manager.stream_status[stream_id]
        stream_status['status'] = 'starting'
        
        # 打开视频流
        retry_count = 0
        max_retries = 10
        retry_interval = 5
        
        while not stop_event.is_set() and retry_count < max_retries:
            try:
                cap = cv2.VideoCapture(stream_url)
                
                if not cap.isOpened():
                    logger.error(f"无法打开视频流: {stream_url}")
                    retry_count += 1
                    time.sleep(retry_interval)
                    continue
                
                # 获取视频参数
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                
                logger.info(f"视频流参数: {frame_width}x{frame_height}, {fps}fps")
                
                # 更新流状态
                stream_status['width'] = frame_width
                stream_status['height'] = frame_height
                stream_status['fps'] = fps
                stream_status['status'] = 'running'
                stream_status['errors'] = 0
                
                # 读取帧
                frame_count = 0
                consecutive_failures = 0
                max_consecutive_failures = 5
                
                while not stop_event.is_set():
                    # 读取一帧
                    ret, frame = cap.read()
                    
                    if not ret:
                        consecutive_failures += 1
                        logger.warning(f"读取视频帧失败 ({consecutive_failures}/{max_consecutive_failures})")
                        
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error("连续多次读取失败，重新连接")
                            break
                            
                        time.sleep(0.1)
                        continue
                    
                    # 重置失败计数
                    consecutive_failures = 0
                    
                    # 将帧放入队列
                    if not ipc_manager.put_frame(stream_id, frame):
                        logger.warning(f"放入帧失败: {stream_id}")
                    
                    frame_count += 1
                    
                    # 防止CPU占用过高
                    if frame_count % 5 == 0:
                        time.sleep(0.001)
                
                # 关闭视频流
                cap.release()
                
            except Exception as e:
                log_exception("stream_process", stream_id, e)
                stream_status['errors'] = stream_status.get('errors', 0) + 1
                
                if cap:
                    cap.release()
                
                time.sleep(retry_interval)
        
        if retry_count >= max_retries:
            stream_status['status'] = 'error'
            logger.error(f"拉流失败次数过多，停止尝试: {stream_id}")
        else:
            stream_status['status'] = 'stopped'
            
    except Exception as e:
        logger.error(f"拉流进程异常: {e}", exc_info=True)
        if stream_id in ipc_manager.stream_status:
            ipc_manager.stream_status[stream_id]['status'] = 'error'
    
    logger.info(f"拉流进程结束: {stream_id}")


# 2. 算法进程
def algorithm_process(stream_id: str, algo_id: str, model_id: str, ipc_manager, model_registry, stop_event, save_alarm: bool = True) -> None:
    """
    算法处理进程，负责从共享队列获取帧，进行算法处理，并将结果放入结果队列。
    Args:
        stream_id: 流ID
        algo_id: 算法ID
        model_id: 模型ID
        ipc_manager: IPC管理器实例
        model_registry: 模型注册表实例
        stop_event: 停止事件
        save_alarm: 是否保存告警图片
    """
    try:
        # 设置进程名
        mp.current_process().name = f"Algo-{stream_id}-{algo_id}"
        
        logger.info(f"启动算法处理进程: {stream_id}, 算法: {algo_id}, 模型: {model_id}")
        
        # 获取模型实例
        model, postprocessor = model_registry.get_model_instance(model_id)
        
        if not model or not postprocessor:
            logger.error(f"无法获取模型实例: {model_id}")
            return
        
        # 创建结果队列
        result_queue = ipc_manager.create_result_queue(stream_id, algo_id)
        
        # 获取算法状态
        algo_status_key = f"{stream_id}_{algo_id}"
        algo_status = ipc_manager.algo_status[algo_status_key]
        algo_status['status'] = 'running'
        
        # 显式打印状态，确认它在被设置
        logger.info(f"算法处理进程状态已设置: {algo_status_key}, 状态列表: {list(ipc_manager.algo_status.keys())}")
        
        # 确保状态可见性（使用共享状态机制）
        ipc_manager.set_shared_status('algo', algo_status_key, algo_status)
        
        # 告警检测参数
        alarm_threshold = 0.6  # 告警阈值
        alarm_cooldown = 10  # 告警冷却时间(秒)
        last_alarm_time = 0  # 上次告警时间
        
        # 临时目录
        temp_dir = os.path.join("temp_frames", stream_id, algo_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # 主循环
        consecutive_empty = 0
        max_consecutive_empty = 50
        first_frame_processed = False
        frame_count = 0
        logger.info(f"算法进程进入主循环，等待处理第一帧...")
        
        # 在algorithm_process主循环内，添加帧计数器，每两帧检测一次
        # 找到while not stop_event.is_set():主循环，添加如下逻辑
        # 伪代码：
        # frame_counter = 0  # 在循环外定义
        # while not stop_event.is_set():
        #     ...
        #     frame_counter += 1
        #     if frame_counter % 2 != 0:
        #         # 释放帧引用，跳过本帧
        #         ipc_manager.memory_manager.release_frame(frame_ref)
        #         continue
        #     # 后续推理处理...
        # 实现为实际代码
        # 获取跳帧间隔配置，默认为2
        cfg = GlobalConfig.instance()
        skip_frame_interval = cfg.get('skip_frame_interval', 2)
        frame_counter = 0
        while not stop_event.is_set():
            try:
                # 获取帧
                frame_ref = ipc_manager.get_frame(stream_id)
                
                if not frame_ref:
                    consecutive_empty += 1
                    if consecutive_empty >= max_consecutive_empty:
                        time.sleep(0.1)
                        consecutive_empty = 0
                    continue
                
                # 跳帧检测逻辑
                frame_counter += 1
                if skip_frame_interval > 1 and (frame_counter % skip_frame_interval != 0):
                    ipc_manager.memory_manager.release_frame(frame_ref)
                    continue
                
                # 重置连续空计数
                consecutive_empty = 0
                
                # 获取帧数据
                frame = ipc_manager.memory_manager.get_frame(frame_ref)
                
                if frame is None:
                    ipc_manager.memory_manager.release_frame(frame_ref)
                    continue
                
                # 更新处理时间
                frame_count += 1
                algo_status['last_process_time'] = time.time()
                
                # 推理
                orig_result, std_result = run_inference(model, frame)
                
                # 后处理
                post_result = run_postprocess(postprocessor, orig_result)
                
                # 创建原始帧的副本，用于绘制检测结果
                processed_frame = frame.copy()
                
                # 在图像上绘制检测结果
                draw_results(processed_frame, post_result)
                
                # 如果是第一帧，设置算法状态为就绪
                if not first_frame_processed:
                    algo_status['status'] = 'ready'
                    algo_status['processed_count'] = frame_count
                    ipc_manager.set_shared_status('algo', algo_status_key, algo_status)
                    logger.info(f"算法处理进程已处理第一帧，状态已设置为ready: {algo_status_key}")
                    first_frame_processed = True
                
                # 处理告警
                last_alarm_time = handle_alarm(ipc_manager, stream_id, algo_id, frame, processed_frame, post_result, temp_dir, last_alarm_time, alarm_cooldown, save_alarm)
                
                # 将结果放入结果队列
                put_result(ipc_manager, stream_id, algo_id, frame_ref, post_result)
                
                # 释放原始帧引用
                ipc_manager.memory_manager.release_frame(frame_ref)
                
            except Exception as e:
                log_exception("algorithm_process", f"{stream_id}_{algo_id}", e)
                algo_status['errors'] = algo_status.get('errors', 0) + 1
                time.sleep(0.1)
        
        algo_status['status'] = 'stopped'
        ipc_manager.set_shared_status('algo', algo_status_key, algo_status)
        
    except Exception as e:
        logger.error(f"算法进程异常: {e}", exc_info=True)
        if algo_status_key in ipc_manager.algo_status:
            algo_status = ipc_manager.algo_status[algo_status_key]
            algo_status['status'] = 'error'
            ipc_manager.set_shared_status('algo', algo_status_key, algo_status)
    
    logger.info(f"算法处理进程结束: {stream_id}, 算法: {algo_id}")


# 3. 推流进程
def streaming_process(stream_id: str, algo_id: str, output_url: str, ipc_manager, stop_event) -> None:
    """
    推流进程，负责从结果队列获取帧，并将其推送到输出流。
    Args:
        stream_id: 流ID
        algo_id: 算法ID
        output_url: 输出流地址
        ipc_manager: IPC管理器实例
        stop_event: 停止事件
    """
    try:
        # 判断输出URL是否为空
        if not output_url:
            logger.error("输出URL为空")
            return
            
        logger.info(f"启动推流进程: {stream_id}, 算法: {algo_id}, 输出: {output_url}")
        
        # 创建进程状态条目
        key = f"{stream_id}_{algo_id}"
        if key not in ipc_manager.output_status:
            output_status = {
                'status': 'starting',
                'last_push_time': 0,
                'frame_count': 0,
                'errors': 0
            }
            ipc_manager.output_status[key] = output_status
            # 写入共享状态
            ipc_manager.set_shared_status('output', key, output_status)
        else:
            output_status = ipc_manager.output_status[key]
        
        # 等待算法处理就绪
        max_wait = 60  # 延长最大等待时间(秒)
        wait_start = time.time()
        check_interval = 2  # 每2秒检查一次并打印日志
        next_log_time = time.time() + check_interval
        
        while (time.time() - wait_start) < max_wait:
            if stop_event.is_set():
                return
                
            # 获取最新的共享算法状态
            algo_status_dict = ipc_manager.get_all_shared_status('algo')
                
            # 检查算法状态
            if key in algo_status_dict:
                algo_status = algo_status_dict[key]
                if algo_status.get('status') == 'ready':
                    logger.info(f"算法处理已就绪: {key}, 状态: {algo_status}")
                    break
                else:
                    logger.info(f"算法状态未就绪: {key}, 当前状态: {algo_status.get('status', 'unknown')}")
            
            # 定期记录等待日志
            current_time = time.time()
            if current_time >= next_log_time:
                logger.info(f"等待算法处理就绪中: {key}，已等待 {int(current_time - wait_start)} 秒")
                # 记录所有状态信息
                logger.info(f"当前算法状态字典: {algo_status_dict}")
                logger.info(f"当前算法状态列表: {list(algo_status_dict.keys())}")
                next_log_time = current_time + check_interval
                
            time.sleep(0.5)
        
        # 检查是否超时
        algo_status_dict = ipc_manager.get_all_shared_status('algo')
        if key not in algo_status_dict or algo_status_dict[key].get('status') != 'ready':
            logger.error(f"等待算法处理就绪超时: {key}")
            logger.error(f"当前所有状态: 算法状态={algo_status_dict}, 流状态={ipc_manager.get_all_shared_status('stream')}")
            output_status['status'] = 'error'
            ipc_manager.set_shared_status('output', key, output_status)
            return
        
        # 等待第一帧
        wait_start = time.time()
        first_result = None
        
        while first_result is None and (time.time() - wait_start) < max_wait:
            if stop_event.is_set():
                return
                
            first_result = ipc_manager.get_result(stream_id, algo_id, timeout=0.5)
        
        if first_result is None:
            logger.error(f"等待首帧超时: {key}")
            output_status['status'] = 'error'
            return
        
        # 获取视频参数
        first_frame_ref = first_result['frame_ref']
        first_frame = ipc_manager.memory_manager.get_frame(first_frame_ref)
        
        if first_frame is None:
            logger.error(f"无法获取首帧: {key}")
            ipc_manager.memory_manager.release_frame(first_frame_ref)
            output_status['status'] = 'error'
            return
        
        frame_height, frame_width = first_frame.shape[:2]
        fps = ipc_manager.stream_status.get(stream_id, {}).get('fps', 25)
        
        # 释放首帧
        ipc_manager.memory_manager.release_frame(first_frame_ref)
        
        # 确定是RTSP还是RTMP推流
        is_rtsp = output_url.startswith("rtsp://")
        is_rtmp = output_url.startswith("rtmp://")
        
        # 检查推流目标地址
        if is_rtsp or is_rtmp:
            # 提取服务器地址和端口
            try:
                # 解析URL
                parts = output_url.split("://")[1].split("/")[0]
                server_address = parts.split(":")[0]
                port = parts.split(":")[1] if ":" in parts else "554" if is_rtsp else "1935"
                
                # 尝试连接服务器
                logger.info(f"检查推流目标服务器: {server_address}:{port}")
                
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                result = s.connect_ex((server_address, int(port)))
                s.close()
                
                if result != 0:
                    logger.error(f"无法连接到推流目标服务器: {server_address}:{port}, 错误代码: {result}")
                    logger.warning(f"继续尝试推流，但可能会失败...")
                else:
                    logger.info(f"成功连接到推流目标服务器: {server_address}:{port}")
            except Exception as e:
                logger.error(f"检查推流目标服务器时出错: {e}")
        
        # 构建FFmpeg命令
        if is_rtsp:
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{frame_width}x{frame_height}',
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-pix_fmt', 'yuv420p',
                '-bufsize', '5000k',
                '-maxrate', '10000k',
                '-g', '15',
                '-x264-params', 'keyint=15:min-keyint=15:scenecut=0:no-cabac=1:8x8dct=0:ref=0',
                '-f', 'rtsp',
                '-rtsp_transport', 'tcp',
                output_url
            ]
        else:
            ffmpeg_cmd = ['ffmpeg', '-y', '-an', # 禁用音频
            '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{frame_width}x{frame_height}', '-r', str(fps), '-i', '-',
            # 进一步优化NVENC参数以降低延迟
            '-c:v', 'h264_nvenc',
            '-preset', 'p1', '-tune', 'll', '-zerolatency', '1', '-delay', '0',
            '-rc', 'cbr', '-rc-lookahead', '0', '-no-scenecut', '1',
            '-b:v', '2M', '-maxrate', '2.5M', '-bufsize', '512k', # 减小缓冲区大小
            '-g', '10', '-keyint_min', '10', # 减少GOP大小以降低延迟
            '-forced-idr', '1', '-surfaces', '1',
            '-profile:v', 'baseline', '-pix_fmt', 'yuv420p',
            # 优化RTSP传输设置
            '-f', 'rtsp', '-rtsp_transport', 'tcp', 
            '-muxdelay', '0.1', # 最小化复用延迟
            output_url]
        
        # 启动FFmpeg进程
        logger.info(f"启动FFmpeg: {' '.join(ffmpeg_cmd)}")
        
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10**6
        )
        
        output_status['status'] = 'running'
        
        # 主循环
        consecutive_empty = 0
        max_consecutive_empty = 30
        ffmpeg_error_count = 0
        max_ffmpeg_errors = 3
        
        retry_delay = 1
        while not stop_event.is_set():
            try:
                # 获取处理后的结果
                result = ipc_manager.get_result(stream_id, algo_id)
                
                if not result:
                    consecutive_empty += 1
                    if consecutive_empty >= max_consecutive_empty:
                        time.sleep(0.1)
                        consecutive_empty = 0
                    continue
                
                # 重置连续空计数
                consecutive_empty = 0
                
                # 获取帧数据
                frame_ref = result['frame_ref']
                frame = ipc_manager.memory_manager.get_frame(frame_ref)
                
                if frame is None:
                    ipc_manager.memory_manager.release_frame(frame_ref)
                    continue
                
                # 更新推流时间
                output_status['last_push_time'] = time.time()
                output_status['frame_count'] = output_status.get('frame_count', 0) + 1
                
                # 检查FFmpeg进程状态
                if ffmpeg_process.poll() is not None:
                    logger.error(f"FFmpeg进程已终止，返回码: {ffmpeg_process.returncode}")
                    try:
                        stderr_output = ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                        logger.error(f"FFmpeg错误输出: {stderr_output}")
                    except Exception as e:
                        logger.error(f"无法读取FFmpeg错误输出: {e}")
                    
                    # 尝试重启FFmpeg
                    ffmpeg_error_count += 1
                    if ffmpeg_error_count >= max_ffmpeg_errors:
                        logger.error(f"FFmpeg错误次数过多，停止尝试")
                        output_status['status'] = 'error'
                        break
                    
                    # 重新启动FFmpeg进程
                    logger.info(f"重新启动FFmpeg进程")
                    try:
                        ffmpeg_process = subprocess.Popen(
                            ffmpeg_cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            bufsize=10**6
                        )
                    except Exception as e:
                        logger.error(f"重启FFmpeg失败: {e}")
                        output_status['status'] = 'error'
                        break
                
                # 将帧写入FFmpeg
                try:
                    ffmpeg_process.stdin.write(frame.tobytes())
                    ffmpeg_process.stdin.flush()
                except Exception as e:
                    log_exception("streaming_process", f"{stream_id}_{algo_id}", e)
                    ffmpeg_error_count += 1
                    if ffmpeg_error_count >= max_ffmpeg_errors:
                        logger.error(f"FFmpeg错误次数过多，停止尝试")
                        output_status['status'] = 'error'
                        break
                    
                    # 尝试重启FFmpeg进程
                    try:
                        if ffmpeg_process.poll() is None:
                            # 尝试正常关闭
                            try:
                                ffmpeg_process.stdin.close()
                                ffmpeg_process.wait(timeout=3)
                            except:
                                # 强制终止
                                try:
                                    ffmpeg_process.terminate()
                                    ffmpeg_process.wait(timeout=1)
                                except:
                                    try:
                                        ffmpeg_process.kill()
                                    except:
                                        pass
                        
                        logger.info(f"重新启动FFmpeg进程")
                        ffmpeg_process = subprocess.Popen(
                            ffmpeg_cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            bufsize=10**6
                        )
                    except Exception as e2:
                        logger.error(f"重启FFmpeg失败: {e2}")
                        output_status['status'] = 'error'
                        break
                
                # 释放帧引用
                ipc_manager.memory_manager.release_frame(frame_ref)
                
            except Exception as e:
                log_exception("streaming_process", f"{stream_id}_{algo_id}", e)
                output_status['errors'] = output_status.get('errors', 0) + 1
                time.sleep(0.1)
                retry_delay = min(retry_delay * 2, 30)
                logger.warning(f"推流重试，{retry_delay}s后重试")
                time.sleep(retry_delay)
                continue
        
        # 关闭FFmpeg进程
        try:
            if ffmpeg_process and ffmpeg_process.poll() is None:
                ffmpeg_process.stdin.close()
                try:
                    ffmpeg_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ffmpeg_process.terminate()
                    try:
                        ffmpeg_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        ffmpeg_process.kill()
        except Exception as e:
            logger.error(f"关闭FFmpeg进程异常: {e}")
        
        output_status['status'] = 'stopped'
        logger.info(f"推流进程结束: {stream_id}, 算法: {algo_id}")
    
    except Exception as e:
        logger.error(f"推流进程整体异常: {e}", exc_info=True)
        key = f"{stream_id}_{algo_id}"
        if key in ipc_manager.output_status:
            ipc_manager.output_status[key]['status'] = 'error'
            ipc_manager.output_status[key]['errors'] = ipc_manager.output_status[key].get('errors', 0) + 1


# 4. 告警进程
def alarm_process(ipc_manager, websocket_url: str, stop_event) -> None:
    """
    告警处理进程，处理告警队列中的告警事件，并通过WebSocket发送告警通知。
    Args:
        ipc_manager: IPC管理器实例
        websocket_url: WebSocket服务器地址
        stop_event: 停止事件
    """
    try:
        # 设置进程名
        mp.current_process().name = f"Alarm-Handler"
        
        logger.info(f"启动告警处理进程, WebSocket: {websocket_url}")
        
        # WebSocket客户端连接
        try:
            import websocket
            import json
            import base64
        except ImportError:
            logger.error("无法导入websocket模块，请安装websocket-client库")
            return
        
        # 尝试连接WebSocket服务器
        ws = None
        reconnect_interval = 5  # 重连间隔(秒)
        
        def connect_websocket():
            try:
                ws = websocket.create_connection(websocket_url)
                logger.info(f"WebSocket连接成功: {websocket_url}")
                return ws
            except Exception as e:
                logger.error(f"WebSocket连接失败: {e}")
                return None
        
        # 主循环
        while not stop_event.is_set():
            # 检查WebSocket连接
            if ws is None:
                ws = connect_websocket()
                if ws is None:
                    time.sleep(reconnect_interval)
                    continue
            
            # 从告警队列获取告警事件
            alarm_data = ipc_manager.get_alarm()
            
            if not alarm_data:
                time.sleep(0.1)
                continue
            
            try:
                # 读取告警图片
                original_img_path = alarm_data.get('original_img_path')
                processed_img_path = alarm_data.get('processed_img_path')
                
                # 将图片编码为base64
                original_img_base64 = ""
                processed_img_base64 = ""
                
                if original_img_path and os.path.exists(original_img_path):
                    with open(original_img_path, "rb") as img_file:
                        original_img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                
                if processed_img_path and os.path.exists(processed_img_path):
                    with open(processed_img_path, "rb") as img_file:
                        processed_img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                
                # 构建WebSocket消息
                message = {
                    'type': 'alarm',
                    'alarm_id': alarm_data.get('alarm_id'),
                    'stream_id': alarm_data.get('stream_id'),
                    'algo_id': alarm_data.get('algo_id'),
                    'timestamp': alarm_data.get('timestamp'),
                    'original_img': original_img_base64,
                    'processed_img': processed_img_base64,
                    'detection_result': alarm_data.get('detection_result')
                }
                
                # 发送WebSocket消息
                try:
                    ws.send(json.dumps(message))
                    logger.info(f"告警消息已发送: {alarm_data.get('alarm_id')}")
                except Exception as e:
                    logger.error(f"WebSocket发送消息失败: {e}")
                    ws.close()
                    ws = None
            
            except Exception as e:
                logger.error(f"处理告警事件异常: {e}", exc_info=True)
        
        # 关闭WebSocket连接
        if ws:
            ws.close()
        
        # 预留告警视频接口
        # def save_alarm_video(...):
        #     pass
    except Exception as e:
        logger.error(f"告警处理进程异常: {e}", exc_info=True)
    
    logger.info("告警处理进程结束")


# 5. 辅助函数
def get_next_frame(ipc_manager, stream_id: str) -> Tuple[Optional[Any], Optional[Any]]:
    """
    从共享队列获取下一帧。
    Args:
        ipc_manager: IPC管理器实例
        stream_id: 流ID
    Returns:
        (帧引用, 帧数据)
    """
    frame_ref = ipc_manager.get_frame(stream_id)
    if not frame_ref:
        return None, None
    frame = ipc_manager.memory_manager.get_frame(frame_ref)
    return frame_ref, frame

def process_frame(model: Any, postprocessor, frame: Any) -> Tuple[Dict, Any]:
    """
    处理单帧，包括推理和后处理。
    Args:
        model: 推理模型实例
        postprocessor: 后处理实例
        frame: 输入帧
    Returns:
        (后处理结果, 处理后的帧)
    """
    orig_result, std_result = run_inference(model, frame)
    post_result = run_postprocess(postprocessor, orig_result)
    processed_frame = frame.copy() if frame is not None else None
    draw_results(processed_frame, post_result)
    return post_result, processed_frame

def handle_alarm(ipc_manager, stream_id: str, algo_id: str, frame: Any, processed_frame: Any, post_result: Dict, temp_dir: str, last_alarm_time: float, alarm_cooldown: int, save_alarm: bool = True) -> float:
    """
    处理告警逻辑，检查是否触发告警并保存图片。
    Args:
        ipc_manager: IPC管理器实例
        stream_id: 流ID
        algo_id: 算法ID
        frame: 原始帧
        processed_frame: 处理后的帧
        post_result: 后处理结果
        temp_dir: 临时文件目录
        last_alarm_time: 上次告警时间
        alarm_cooldown: 告警冷却时间(秒)
        save_alarm: 是否保存告警图片
    Returns:
        更新后的上次告警时间
    """
    current_time = time.time()
    has_alarm = check_alarm(post_result)
    if has_alarm and (current_time - last_alarm_time > alarm_cooldown) and save_alarm:
        from datetime import datetime
        import uuid
        last_alarm_time = current_time
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        alarm_id = f"alarm_{timestamp}_{uuid.uuid4().hex[:8]}"
        original_img_path = os.path.join(temp_dir, f"{alarm_id}_original.jpg")
        processed_img_path = os.path.join(temp_dir, f"{alarm_id}_processed.jpg")
        import cv2
        cv2.imwrite(original_img_path, frame)
        cv2.imwrite(processed_img_path, processed_frame)
        alarm_data = {
            'alarm_id': alarm_id,
            'stream_id': stream_id,
            'algo_id': algo_id,
            'timestamp': current_time,
            'original_img_path': original_img_path,
            'processed_img_path': processed_img_path,
            'detection_result': post_result
        }
        ipc_manager.put_alarm(alarm_data)
    return last_alarm_time

def put_result(ipc_manager, stream_id: str, algo_id: str, frame_ref: Any, post_result: Dict) -> None:
    """
    将处理结果放入结果队列。
    Args:
        ipc_manager: IPC管理器实例
        stream_id: 流ID
        algo_id: 算法ID
        frame_ref: 帧引用
        post_result: 后处理结果
    """
    result_data = {
        'frame_id': frame_ref.frame_id,
        'timestamp': frame_ref.timestamp,
        'detection_result': post_result
    }
    ipc_manager.put_result(stream_id, algo_id, frame_ref, result_data)

def draw_results(frame: Any, results: Dict, draw_strategy: Optional[Callable[[Any, Dict], Any]] = None) -> Any:
    """
    在图像上绘制检测结果，支持自定义绘制策略。
    Args:
        frame: 输入帧
        results: 检测结果字典
        draw_strategy: 可选，自定义绘制函数
    Returns:
        绘制后的帧
    """
    if draw_strategy:
        return draw_strategy(frame, results)
    try:
        for rect in results['data']['bbox']['rectangles']:
            x1, y1, x2, y2 = rect['xyxy']
            color = rect['color']
            label = rect.get('label', '')
            conf = rect.get('conf', 0)
            import cv2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            text = f"{label} {conf:.2f}"
            cv2.putText(frame, text, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        for poly_id, poly_data in results['data']['bbox']['polygons'].items():
            import numpy as np
            points = np.array(poly_data['polygon'], np.int32)
            points = points.reshape((-1, 1, 2))
            color = poly_data.get('color', [0, 255, 0])
            cv2.polylines(frame, [points], True, color, 2)
    except Exception as e:
        log_exception("draw_results", "-", e)
    return frame

def check_alarm(results: Dict, alarm_strategy: Optional[Callable[[Dict], bool]] = None, threshold: float = 0.6) -> bool:
    """
    检查是否触发告警，支持自定义告警策略。
    Args:
        results: 后处理结果字典
        alarm_strategy: 可选，自定义告警策略函数
        threshold: 告警阈值
    Returns:
        True表示触发告警，False表示未触发
    """
    if alarm_strategy:
        return alarm_strategy(results)
    try:
        for rect in results['data']['bbox']['rectangles']:
            conf = rect.get('conf', 0)
            if conf >= threshold:
                return True
        return False
    except:
        return False 

def adjust_ffmpeg_params(ffmpeg_params: Dict, network_status: Optional[Dict] = None) -> Dict:
    """
    根据网络状况动态调整推流参数（预留接口）。
    Args:
        ffmpeg_params: 当前FFmpeg参数字典
        network_status: 网络状态字典，包含延迟、带宽等信息
    Returns:
        调整后的FFmpeg参数字典
    """
    # 目前不做实际调整，后续可根据network_status动态修改ffmpeg_params
    return ffmpeg_params 