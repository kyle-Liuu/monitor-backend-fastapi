"""
YOLOv8统一模型实现
- 继承BaseModel基类
- 实现标准化的模型接口
- 支持自动预热和资源管理
"""

import cv2
import numpy as np
import torch
import os
import logging
from ultralytics import YOLO
from typing import Dict, List, Any, Tuple

# 导入基类
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from base_classes import BaseModel

logger = logging.getLogger(__name__)

class YOLOv8UnifiedModel(BaseModel):
    """YOLOv8统一模型实现"""
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        初始化YOLOv8模型
        Args:
            model_config: 模型配置字典
        """
        # 设置默认参数
        self.default_config = {
            'img_size': 640,
            'conf_thres': 0.25,
            'iou_thres': 0.45,
            'max_det': 20,
            'model_file': 'yolov8n.pt',
        }
        
        # 合并配置
        merged_config = {**self.default_config, **model_config}
        super().__init__(merged_config)
    
    def _load_model(self):
        """加载YOLOv8模型"""
        try:
            # 获取模型文件路径
            model_file = self.config.get('model_file', 'yolov8n.pt')
            model_path = os.path.join(os.path.dirname(__file__), 'yolov8_model', model_file)
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")
            
            # 加载模型
            self.model = YOLO(model_path)
            logger.info(f"YOLOv8模型加载成功: {model_file}")
            
        except Exception as e:
            logger.error(f"加载YOLOv8模型失败: {e}")
            raise
    
    def _warmup(self):
        """模型预热"""
        try:
            # 创建随机测试图像
            dummy_image = np.random.randint(0, 255, (self.config['img_size'], self.config['img_size'], 3), dtype=np.uint8)
            
            # 执行一次推理进行预热
            _ = self.model(
                dummy_image,
                conf=self.config['conf_thres'],
                iou=self.config['iou_thres'],
                device=self.device,
                max_det=1
            )
            
            logger.info("YOLOv8模型预热完成")
            
        except Exception as e:
            logger.warning(f"YOLOv8模型预热失败: {e}")
    
    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float, int, int, Tuple[int, int]]:
        """
        图像预处理
        Args:
            image: 输入图像 (BGR格式)
        Returns:
            Tuple[预处理图像, 缩放比例, 填充宽度, 填充高度, 原始尺寸]
        """
        if image is None or image.size == 0:
            raise ValueError("输入图像为空")
        
        # BGR转RGB
        if image.shape[-1] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image
        
        # letterbox处理
        img_padded, ratio, padw, padh = self._letterbox(
            img_rgb, 
            (self.config['img_size'], self.config['img_size'])
        )
        
        return img_padded, ratio, padw, padh, img_rgb.shape[:2]
    
    def _letterbox(self, img: np.ndarray, new_shape: Tuple[int, int] = (640, 640), color: Tuple[int, int, int] = (114, 114, 114)) -> Tuple[np.ndarray, float, int, int]:
        """
        Letterbox处理
        Args:
            img: 输入图像
            new_shape: 目标尺寸
            color: 填充颜色
        Returns:
            Tuple[处理后图像, 缩放比例, 填充宽度, 填充高度]
        """
        shape = img.shape[:2]  # 当前尺寸 [height, width]
        ratio = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))
        
        # 缩放图像
        img_resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        
        # 计算填充
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        dw /= 2
        dh /= 2
        
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        
        # 添加填充
        img_padded = cv2.copyMakeBorder(
            img_resized, top, bottom, left, right, 
            cv2.BORDER_CONSTANT, value=color
        )
        
        return img_padded, ratio, left, top
    
    def _to_standard_results(self, results, ratio: float, padw: int, padh: int, orig_shape: Tuple[int, int]) -> List[Dict]:
        """
        转换为标准化结果
        Args:
            results: YOLOv8原始结果
            ratio: 缩放比例
            padw: 填充宽度
            padh: 填充高度
            orig_shape: 原始图像尺寸
        Returns:
            标准化结果列表
        """
        standard_results = []
        
        try:
            # 处理检测结果
            if hasattr(results[0], 'boxes') and results[0].boxes is not None:
                boxes = results[0].boxes
                
                for i in range(len(boxes)):
                    # 获取边界框坐标
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    
                    # 坐标反变换（从填充图像坐标转换回原图坐标）
                    x1, y1, x2, y2 = xyxy
                    x1 = (x1 - padw) / ratio
                    y1 = (y1 - padh) / ratio
                    x2 = (x2 - padw) / ratio
                    y2 = (y2 - padh) / ratio
                    
                    # 确保坐标在有效范围内
                    x1 = max(0, min(x1, orig_shape[1]))
                    y1 = max(0, min(y1, orig_shape[0]))
                    x2 = max(0, min(x2, orig_shape[1]))
                    y2 = max(0, min(y2, orig_shape[0]))
                    
                    # 获取置信度和类别
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls = int(boxes.cls[i].cpu().numpy())
                    
                    # 构建标准化结果
                    result = {
                        'xyxy': [x1, y1, x2, y2],
                        'conf': conf,
                        'label': cls,
                        'bbox': [x1, y1, x2 - x1, y2 - y1]  # [x, y, w, h]
                    }
                    
                    standard_results.append(result)
        
        except Exception as e:
            logger.error(f"转换标准化结果失败: {e}")
        
        return standard_results
    
    def infer(self, image: np.ndarray) -> Tuple[Any, List[Dict]]:
        """
        执行推理
        Args:
            image: 输入图像 (BGR格式)
        Returns:
            Tuple[原始结果, 标准化结果列表]
        """
        if not self.model:
            logger.error("模型未加载")
            return None, []
        
        try:
            # 预处理
            img_padded, ratio, padw, padh, orig_shape = self._preprocess(image)
            
            # 执行推理
            results = self.model(
                img_padded,
                conf=self.config['conf_thres'],
                iou=self.config['iou_thres'],
                device=self.device,
                max_det=self.config['max_det']
            )
            
            # 转换为标准化结果
            standard_results = self._to_standard_results(results, ratio, padw, padh, orig_shape)
            
            return results, standard_results
            
        except Exception as e:
            logger.error(f"YOLOv8推理失败: {e}")
            return None, []


def create_model(model_config: Dict[str, Any]) -> YOLOv8UnifiedModel:
    """
    创建YOLOv8模型实例
    Args:
        model_config: 模型配置
    Returns:
        YOLOv8模型实例
    """
    return YOLOv8UnifiedModel(model_config) 