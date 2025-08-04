"""
改进的简化YOLOv8模型实现
- 支持继承基类（可选）
- 保持简单易用
- 适合非专业人员和专业人员
"""

import cv2
import numpy as np
import torch
import os
import logging
from typing import Dict, List, Any, Tuple
from ultralytics import YOLO

# 尝试导入基类（可选）
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from base_classes import BaseModel
    HAS_BASE_CLASS = True
except ImportError:
    HAS_BASE_CLASS = False

logger = logging.getLogger(__name__)

class SimpleYOLODetector:
    """简化的YOLOv8检测器 - 基础版本"""
    
    def __init__(self, name, conf):
        """
        初始化检测器
        Args:
            name: 模型名称
            conf: 配置字典
        """
        self.name = name
        self.conf = conf
        self.model = None
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        self.is_warmed_up = False
        
        # 加载模型
        self._load_model()
        
        # 预热模型
        self._warmup()
    
    def _load_model(self):
        """加载模型"""
        try:
            # 模型文件路径
            model_path = os.path.join(os.path.dirname(__file__), 'yolov8_model', 'yolov8n.pt')
            
            if not os.path.exists(model_path):
                logger.error(f"模型文件不存在: {model_path}")
                return
            
            # 加载模型
            self.model = YOLO(model_path)
            logger.info(f"模型加载成功: {model_path}")
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
    
    def _warmup(self):
        """模型预热"""
        try:
            # 创建测试图像
            test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # 执行一次推理
            _ = self.model(test_image, conf=0.25, iou=0.45, device=self.device)
            self.is_warmed_up = True
            logger.info("模型预热完成")
            
        except Exception as e:
            logger.warning(f"模型预热失败: {e}")
    
    def infer(self, image):
        """
        执行推理
        Args:
            image: 输入图像 (BGR格式)
        Returns:
            Tuple[原始结果, 标准化结果]
        """
        try:
            # 执行推理
            results = self.model(image, conf=0.25, iou=0.45, device=self.device)
            
            # 转换为标准化结果
            standard_results = self._to_standard_results(results, image.shape)
            
            return results, standard_results
            
        except Exception as e:
            logger.error(f"推理失败: {e}")
            return None, []
    
    def _to_standard_results(self, results, image_shape):
        """
        转换为标准化结果
        Args:
            results: YOLOv8原始结果
            image_shape: 图像尺寸
        Returns:
            标准化结果列表
        """
        standard_results = []
        
        try:
            if hasattr(results[0], 'boxes') and results[0].boxes is not None:
                boxes = results[0].boxes
                
                for i in range(len(boxes)):
                    # 获取坐标
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())
                    cls = int(boxes.cls[i].cpu().numpy())
                    
                    # 构建结果
                    result = {
                        'xyxy': [float(x) for x in xyxy],
                        'conf': conf,
                        'label': cls
                    }
                    
                    standard_results.append(result)
        
        except Exception as e:
            logger.error(f"转换结果失败: {e}")
        
        return standard_results
    
    def release(self):
        """释放资源"""
        if self.model:
            del self.model
            self.model = None
        logger.info("模型资源已释放")


# 如果基类可用，创建继承版本
if HAS_BASE_CLASS:
    class StandardYOLODetector(BaseModel):
        """标准YOLOv8检测器 - 继承基类版本"""
        
        def __init__(self, model_config: Dict[str, Any]):
            """
            初始化标准检测器
            Args:
                model_config: 模型配置字典
            """
            super().__init__(model_config)
        
        def _load_model(self):
            """加载模型 - 实现基类抽象方法"""
            try:
                # 获取模型文件路径
                model_file = self.config.get('model_file', 'yolov8n.pt')
                model_path = os.path.join(os.path.dirname(__file__), 'yolov8_model', model_file)
                
                if not os.path.exists(model_path):
                    raise FileNotFoundError(f"模型文件不存在: {model_path}")
                
                # 加载模型
                self.model = YOLO(model_path)
                logger.info(f"标准模型加载成功: {model_path}")
                
            except Exception as e:
                logger.error(f"标准模型加载失败: {e}")
                raise
        
        def _warmup(self):
            """模型预热 - 实现基类抽象方法"""
            try:
                # 获取配置参数
                img_size = self.config.get('img_size', 640)
                conf_thres = self.config.get('conf_thres', 0.25)
                iou_thres = self.config.get('iou_thres', 0.45)
                
                # 创建测试图像
                test_image = np.random.randint(0, 255, (img_size, img_size, 3), dtype=np.uint8)
                
                # 执行一次推理
                _ = self.model(test_image, conf=conf_thres, iou=iou_thres, device=self.device)
                logger.info("标准模型预热完成")
                
            except Exception as e:
                logger.warning(f"标准模型预热失败: {e}")
        
        def infer(self, image: np.ndarray) -> Tuple[Any, List[Dict]]:
            """
            执行推理 - 实现基类抽象方法
            Args:
                image: 输入图像 (BGR格式)
            Returns:
                Tuple[原始结果, 标准化结果列表]
            """
            try:
                # 获取配置参数
                conf_thres = self.config.get('conf_thres', 0.25)
                iou_thres = self.config.get('iou_thres', 0.45)
                max_det = self.config.get('max_det', 20)
                
                # 执行推理
                results = self.model(
                    image, 
                    conf=conf_thres, 
                    iou=iou_thres, 
                    device=self.device,
                    max_det=max_det
                )
                
                # 转换为标准化结果
                standard_results = self._to_standard_results(results, image.shape)
                
                return results, standard_results
                
            except Exception as e:
                logger.error(f"标准推理失败: {e}")
                return None, []
        
        def _to_standard_results(self, results, image_shape):
            """转换为标准化结果"""
            standard_results = []
            
            try:
                if hasattr(results[0], 'boxes') and results[0].boxes is not None:
                    boxes = results[0].boxes
                    
                    for i in range(len(boxes)):
                        # 获取坐标
                        xyxy = boxes.xyxy[i].cpu().numpy()
                        conf = float(boxes.conf[i].cpu().numpy())
                        cls = int(boxes.cls[i].cpu().numpy())
                        
                        # 构建结果
                        result = {
                            'xyxy': [float(x) for x in xyxy],
                            'conf': conf,
                            'label': cls
                        }
                        
                        standard_results.append(result)
            
            except Exception as e:
                logger.error(f"转换结果失败: {e}")
            
            return standard_results


def create_model(name, conf, use_base_class=False):
    """
    创建模型实例
    Args:
        name: 模型名称
        conf: 配置字典
        use_base_class: 是否使用基类版本
    Returns:
        模型实例
    """
    if use_base_class and HAS_BASE_CLASS:
        logger.info("使用标准版本（继承基类）")
        return StandardYOLODetector(conf)
    else:
        logger.info("使用简化版本（基础实现）")
        return SimpleYOLODetector(name, conf) 