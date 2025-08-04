"""
YOLOv8统一算法包实现
- 继承BaseAlgorithmPackage基类
- 实现标准化的算法包接口
- 支持自动解压缩、校验和导入
"""

import os
import sys
import logging
from typing import Dict, Any, Tuple
from pathlib import Path

# 添加基类路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from base_classes import BaseAlgorithmPackage, BaseModel, BasePostprocessor

# 导入具体的模型和后处理器实现
from model.yolov8_model_unified import YOLOv8UnifiedModel, create_model
from postprocessor.yolov8_postprocessor_unified import YOLOv8UnifiedPostprocessor, create_postprocessor

logger = logging.getLogger(__name__)

class YOLOv8AlgorithmPackage(BaseAlgorithmPackage):
    """YOLOv8算法包实现"""
    
    def __init__(self, package_path: str):
        """
        初始化YOLOv8算法包
        Args:
            package_path: 算法包路径
        """
        super().__init__(package_path)
        logger.info(f"YOLOv8算法包初始化: {self.package_id}")
    
    def create_model(self, model_config: Dict[str, Any]) -> BaseModel:
        """
        创建YOLOv8模型实例
        Args:
            model_config: 模型配置
        Returns:
            YOLOv8模型实例
        """
        try:
            # 合并默认配置和用户配置
            default_config = {
                'img_size': 640,
                'conf_thres': 0.25,
                'iou_thres': 0.45,
                'max_det': 20,
                'model_file': 'yolov8n.pt',
            }
            
            merged_config = {**default_config, **model_config}
            return create_model(merged_config)
            
        except Exception as e:
            logger.error(f"创建YOLOv8模型失败: {e}")
            raise
    
    def create_postprocessor(self, postprocessor_config: Dict[str, Any]) -> BasePostprocessor:
        """
        创建YOLOv8后处理器实例
        Args:
            postprocessor_config: 后处理器配置
        Returns:
            YOLOv8后处理器实例
        """
        try:
            # 合并默认配置和用户配置
            default_config = {
                'conf_threshold': 0.25,
                'label_whitelist': None,
                'color': [0, 255, 0],
                'draw_bbox': True,
                'draw_label': True,
                'draw_conf': True,
                'output_format': 'standard'
            }
            
            merged_config = {**default_config, **postprocessor_config}
            return create_postprocessor(merged_config)
            
        except Exception as e:
            logger.error(f"创建YOLOv8后处理器失败: {e}")
            raise
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证YOLOv8算法包
        Returns:
            Tuple[是否有效, 错误信息]
        """
        try:
            # 基础验证
            is_valid, error_msg = super().validate()
            if not is_valid:
                return False, error_msg
            
            # YOLOv8特定验证
            model_file = self.model_config.get("model_file", "yolov8n.pt")
            model_path = self.package_path / "model" / "yolov8_model" / model_file
            
            if not model_path.exists():
                return False, f"YOLOv8模型文件不存在: {model_file}"
            
            # 检查模型文件大小
            if model_path.stat().st_size < 1024:  # 小于1KB
                return False, f"YOLOv8模型文件可能损坏: {model_file}"
            
            # 检查配置文件
            required_config_keys = ["algorithm_type", "device_type"]
            for key in required_config_keys:
                if key not in self.model_config:
                    return False, f"模型配置缺少必要字段: {key}"
            
            return True, "YOLOv8算法包验证通过"
            
        except Exception as e:
            return False, f"YOLOv8算法包验证失败: {str(e)}"
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        Returns:
            模型信息字典
        """
        return {
            "algorithm_type": "YOLOv8",
            "model_file": self.model_config.get("model_file", "yolov8n.pt"),
            "input_size": self.model_config.get("img_size", 640),
            "device_type": self.model_config.get("device_type", "cpu,gpu"),
            "default_conf_threshold": self.model_config.get("conf_thres", 0.25),
            "default_iou_threshold": self.model_config.get("iou_thres", 0.45),
            "max_detections": self.model_config.get("max_det", 20)
        }
    
    def get_postprocessor_info(self) -> Dict[str, Any]:
        """
        获取后处理器信息
        Returns:
            后处理器信息字典
        """
        return {
            "postprocessor_type": "YOLOv8Detection",
            "output_format": self.postprocessor_config.get("output_format", "standard"),
            "default_conf_threshold": self.postprocessor_config.get("conf_threshold", 0.25),
            "supported_features": ["bbox_detection", "confidence_filtering", "label_filtering", "result_drawing"],
            "color_scheme": self.postprocessor_config.get("color", [0, 255, 0])
        }
    
    def get_package_info(self) -> Dict[str, Any]:
        """
        获取算法包完整信息
        Returns:
            算法包信息字典
        """
        return {
            **self.metadata,
            "model_info": self.get_model_info(),
            "postprocessor_info": self.get_postprocessor_info(),
            "package_path": str(self.package_path),
            "validation_status": "valid" if self.validate()[0] else "invalid"
        }


def create_algorithm_package(package_path: str) -> YOLOv8AlgorithmPackage:
    """
    创建YOLOv8算法包实例
    Args:
        package_path: 算法包路径
    Returns:
        YOLOv8算法包实例
    """
    return YOLOv8AlgorithmPackage(package_path)


# 工厂函数，用于动态创建算法包
def create_package(package_path: str) -> BaseAlgorithmPackage:
    """
    工厂函数：根据包路径创建对应的算法包实例
    Args:
        package_path: 算法包路径
    Returns:
        算法包实例
    """
    package_id = Path(package_path).name
    
    # 根据包ID判断算法类型
    if package_id.startswith("algo") and "yolo" in package_id.lower():
        return YOLOv8AlgorithmPackage(package_path)
    else:
        # 默认返回YOLOv8算法包
        return YOLOv8AlgorithmPackage(package_path) 