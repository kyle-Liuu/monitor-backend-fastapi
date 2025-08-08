#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CUDA加速实时检测脚本 - 使用算法包
- 使用算法包中的OptimizedYOLOv8Detector
- 使用算法包中的OptimizedYOLOv8Postprocessor
- GPU推理优化
- 实时RTSP推流
"""

import cv2
import numpy as np
import time
import os
import sys
import logging
import subprocess
import threading
from typing import Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from algorithms.installed.algocf6c488d.model.simple_yolo import SimpleYOLODetector
from algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor import SimplePostprocessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AlgorithmPackageDetector:
    """使用算法包的检测器"""
    
    def __init__(self, rtsp_input: str, rtsp_output: str):
        """
        初始化检测器
        
        Args:
            rtsp_input: RTSP输入地址
            rtsp_output: RTSP输出地址
        """
        self.rtsp_input = rtsp_input
        self.rtsp_output = rtsp_output
        self.running = False
        
        # 视频处理
        self.cap = None
        self.ffmpeg_process = None
        
        # 算法包组件
        self.model = None
        self.postprocessor = None
        
        # 跳帧检测
        self.frame_skip = 2  # 每3帧检测一次
        self.frame_counter = 0
        
        # 统计
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = None
        
        # 性能统计
        self.preprocess_times = []
        self.inference_times = []
        self.postprocess_times = []
        self.total_times = []
        
        # 帧缓存
        self.last_detection_results = None
        self.last_detection_frame = None
        
        logger.info("算法包检测器初始化完成")
        logger.info(f"输入地址: {rtsp_input}")
        logger.info(f"输出地址: {rtsp_output}")
        logger.info(f"跳帧设置: 每{self.frame_skip + 1}帧检测一次")
    
    def load_algorithm_package(self):
        """加载算法包"""
        try:
            # 导入算法包组件
            # from algorithms.installed.algocf6c488d.model.yolov8_detect_optimized import OptimizedYOLOv8Detector
            # from algorithms.installed.algocf6c488d.postprocessor.yolov8_detection_optimized import OptimizedYOLOv8Postprocessor
            
            # 模型配置
            model_conf = {
                'args': {
                    'img_size': 640,
                    'conf_thres': 0.25,
                    'iou_thres': 0.45,
                    'max_det': 20,
                    'model_file': 'yolov8n.pt',
                    'batch_size': 1,
                    'half_precision': True,
                    'enable_tensorrt': False,
                    'enable_cuda_graph': False,
                    'warmup_frames': 5,
                    'preprocess_mode': 'letterbox',
                    'normalize': True,
                    'auto_contrast': True,
                    'blur_detection': True
                }
            }
            
            # 后处理器配置
            postprocessor_conf = {
                'conf_thres': 0.25,
                'strategy': 'bottom',
                'polygons': {}
            }
            
            # 创建模型
            self.model = SimpleYOLODetector('yolov8_detector', model_conf)
            
            # 创建后处理器
            self.postprocessor = SimplePostprocessor('test_source', 'yolov8_detector', postprocessor_conf)
            
            logger.info("算法包加载成功")
            return True
            
        except Exception as e:
            logger.error(f"加载算法包失败: {e}")
            return False
    
    def init_video(self):
        """初始化视频流"""
        try:
            # 初始化输入流
            self.cap = cv2.VideoCapture(self.rtsp_input)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 减少缓冲
            self.cap.set(cv2.CAP_PROP_FPS, 25)  # 设置帧率
            
            if not self.cap.isOpened():
                logger.error(f"无法打开输入流: {self.rtsp_input}")
                return False
            
            # 获取视频参数
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"输入流参数: {width}x{height}, {fps}fps")
            
            # 启动优化的FFmpeg推流进程
            if not self._start_optimized_ffmpeg_push(width, height, fps):
                logger.error("启动FFmpeg推流失败")
                return False
            
            logger.info("视频流初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"初始化视频流失败: {e}")
            return False
    
    def _start_optimized_ffmpeg_push(self, width, height, fps):
        """启动优化的FFmpeg推流"""
        try:
            # 使用更稳定的推流参数
            ffmpeg_cmd = [
            'ffmpeg', '-y', '-an', # 禁用音频
            '-f', 'rawvideo', '-vcodec', 'rawvideo', '-pix_fmt', 'bgr24',
            '-s', f'{width}x{height}', '-r', str(fps), '-i', '-',
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
            self.rtsp_output
        ]
            
            logger.info(f"优化FFmpeg命令: {' '.join(ffmpeg_cmd)}")
            
            # 启动FFmpeg进程
            self.ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0  # 禁用缓冲
            )
            
            # 等待一下确保FFmpeg启动
            time.sleep(3)
            
            if self.ffmpeg_process.poll() is not None:
                # FFmpeg进程已经退出
                stderr_output = self.ffmpeg_process.stderr.read().decode()
                logger.error(f"FFmpeg启动失败: {stderr_output}")
                return False
            
            logger.info("优化FFmpeg推流进程启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动FFmpeg失败: {e}")
            return False
    
    def algorithm_inference(self, frame):
        """使用算法包进行推理，返回标准化结果"""
        try:
            start_time = time.time()
            # 使用算法包模型进行推理，返回ultralytics原始结果和标准化结果
            _, std_results = self.model.infer(frame)
            inference_time = time.time() - start_time
            self.inference_times.append(inference_time)
            return std_results, inference_time
        except Exception as e:
            logger.error(f"算法推理失败: {e}")
            return [], 0
    
    def algorithm_postprocess(self, frame, std_results):
        """使用算法包进行后处理，直接处理标准化结果"""
        try:
            start_time = time.time()
            if not std_results:
                return frame, 0
            # 使用算法包后处理器，直接传入标准化结果
            postprocess_result = self.postprocessor.process(std_results)
            # 绘制检测结果
            frame = self._draw_detection_results(frame, postprocess_result)
            postprocess_time = time.time() - start_time
            self.postprocess_times.append(postprocess_time)
            return frame, postprocess_time
        except Exception as e:
            logger.error(f"算法后处理失败: {e}")
            return frame, 0
            
    def _draw_detection_results(self, frame, postprocess_result):
        """绘制检测结果"""
        try:
            # 获取检测数据
            data = postprocess_result.get('data', {})
            bbox_data = data.get('bbox', {})
                
            # 绘制矩形框
            rectangles = bbox_data.get('rectangles', [])
            for rect in rectangles:
                if 'xyxy' in rect and 'color' in rect:
                    x1, y1, x2, y2 = rect['xyxy']
                    color = rect['color']
                    label = rect.get('label', '')
                    conf = rect.get('conf', 0)
                    
                    # 绘制矩形框
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), 
                                (int(color[0]), int(color[1]), int(color[2])), 2)
                    
                    # 绘制标签和置信度
                    if label and conf > 0:
                        text = f"{label} {conf:.2f}"
                        cv2.putText(frame, text, (int(x1), int(y1) - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                                  (int(color[0]), int(color[1]), int(color[2])), 2)
            
            # 输出检测信息
            if rectangles:
                logger.info(f"检测到 {len(rectangles)} 个目标")
            
            return frame
            
        except Exception as e:
            logger.error(f"绘制检测结果失败: {e}")
            return frame
    
    def should_detect_frame(self):
        """判断是否应该检测当前帧"""
        return self.frame_counter % (self.frame_skip + 1) == 0
    
    def run(self, duration: int = 60):
        """
        运行检测
        
        Args:
            duration: 测试持续时间(秒)
        """
        logger.info(f"开始运行算法包检测，持续时间: {duration}秒")
        
        # 加载算法包
        if not self.load_algorithm_package():
            logger.error("算法包加载失败")
            return False
        
        # 初始化视频流
        if not self.init_video():
            logger.error("视频流初始化失败")
            return False
        
        # 开始检测
        self.running = True
        self.start_time = time.time()
        
        try:
            while self.running:
                # 检查是否超时
                if time.time() - self.start_time > duration:
                    logger.info("测试时间到，停止运行")
                    break
                
                # 检查FFmpeg进程是否还在运行
                if self.ffmpeg_process and self.ffmpeg_process.poll() is not None:
                    logger.error("FFmpeg进程已退出")
                    break
                
                # 读取帧
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("读取帧失败")
                    time.sleep(0.1)
                    continue
                
                # 增加帧计数器
                self.frame_counter += 1
                
                # 判断是否进行检测
                if self.should_detect_frame():
                    # 进行检测
                    std_results, inference_time = self.algorithm_inference(frame)
                    frame, postprocess_time = self.algorithm_postprocess(frame, std_results)
                    
                    # 缓存检测结果
                    self.last_detection_results = std_results
                    self.last_detection_frame = frame.copy()
                    
                    self.detection_count += 1
                else:
                    # 使用上一帧的检测结果
                    if self.last_detection_results is not None:
                        frame, _ = self.algorithm_postprocess(frame, self.last_detection_results)
                    
                    inference_time = postprocess_time = 0
                
                # 推流到FFmpeg - 添加重试机制
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                            self.ffmpeg_process.stdin.write(frame.tobytes())
                            self.ffmpeg_process.stdin.flush()
                            break  # 成功推流，跳出重试循环
                        else:
                            logger.error("FFmpeg进程已退出")
                            break
                    except Exception as e:
                        if retry == max_retries - 1:
                            logger.error(f"推流失败，已重试{max_retries}次: {e}")
                            break
                        else:
                            logger.warning(f"推流失败，重试{retry + 1}/{max_retries}: {e}")
                            time.sleep(0.1)
                
                # 统计
                self.frame_count += 1
                
                # 计算总时间
                total_time = inference_time + postprocess_time
                self.total_times.append(total_time)
                
                # 输出性能统计
                if self.frame_count % 30 == 0:  # 每30帧输出一次
                    elapsed_time = time.time() - self.start_time
                    fps = self.frame_count / elapsed_time
                    
                    avg_total = np.mean(self.total_times[-30:]) * 1000 if self.total_times else 0
                    
                    logger.info(f"性能统计: FPS={fps:.2f}, "
                               f"总处理时间={avg_total:.1f}ms, "
                               f"检测次数={self.detection_count}, "
                               f"跳帧率={self.frame_skip/(self.frame_skip+1)*100:.1f}%")
                
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        except Exception as e:
            logger.error(f"运行异常: {e}")
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """停止检测"""
        logger.info("停止检测")
        self.running = False
        
        # 停止FFmpeg进程
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.stdin.close()
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=5)
                logger.info("FFmpeg进程已停止")
            except Exception as e:
                logger.error(f"停止FFmpeg进程失败: {e}")
        
        # 释放资源
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # 释放算法包资源
        if self.model:
            self.model.release()
        
        # 输出最终统计
        if self.start_time and self.frame_count > 0:
            elapsed_time = time.time() - self.start_time
            fps = self.frame_count / elapsed_time
            detection_rate = self.detection_count / self.frame_count * 100
            
            logger.info("\n" + "="*60)
            logger.info("最终性能统计")
            logger.info("="*60)
            
            if self.inference_times:
                avg_inference = np.mean(self.inference_times) * 1000
                logger.info(f"平均推理时间: {avg_inference:.2f}ms")
            
            if self.postprocess_times:
                avg_postprocess = np.mean(self.postprocess_times) * 1000
                logger.info(f"平均后处理时间: {avg_postprocess:.2f}ms")
            
            if self.total_times:
                avg_total = np.mean(self.total_times) * 1000
                logger.info(f"平均总处理时间: {avg_total:.2f}ms")
            
            logger.info(f"总处理帧数: {self.frame_count}")
            logger.info(f"检测次数: {self.detection_count}")
            logger.info(f"平均FPS: {fps:.2f}")
            logger.info(f"检测率: {detection_rate:.2f}%")
            logger.info(f"跳帧设置: 每{self.frame_skip + 1}帧检测一次")

def main():
    """主函数"""
    # RTSP地址
    rtsp_input = "rtsp://192.168.1.186/live/test"
    rtsp_output = "rtsp://192.168.1.186/live/detect"
    
    # 创建检测器
    detector = AlgorithmPackageDetector(rtsp_input, rtsp_output)
    
    # 运行检测
    try:
        detector.run(duration=600)  # 运行600秒
    except Exception as e:
        logger.error(f"检测失败: {e}")

if __name__ == "__main__":
    main() 