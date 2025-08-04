"""
算法包管理器
- 自动选择简化版本或标准版本
- 支持配置驱动的版本选择
- 提供统一的算法包接口
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple

# 导入模型和后处理器
from .model.simple_yolo_improved import create_model
from .postprocessor.simple_postprocessor_improved import create_postprocessor

logger = logging.getLogger(__name__)

class AlgorithmPackageManager:
    """算法包管理器"""
    
    def __init__(self, package_path: str = None):
        """
        初始化算法包管理器
        Args:
            package_path: 算法包路径
        """
        self.package_path = package_path or os.path.dirname(__file__)
        self.config = self._load_config()
        
        # 版本选择策略
        self.use_base_class = self.config.get('use_base_class', False)
        self.auto_detect = self.config.get('auto_detect', True)
        
        logger.info(f"算法包管理器初始化: {self.package_path}")
        logger.info(f"使用基类: {self.use_base_class}")
        logger.info(f"自动检测: {self.auto_detect}")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        config = {
            'use_base_class': False,  # 默认使用简化版本
            'auto_detect': True,      # 自动检测基类可用性
            'model_config': {
                'img_size': 640,
                'conf_thres': 0.25,
                'iou_thres': 0.45,
                'max_det': 20,
                'model_file': 'yolov8n.pt'
            },
            'postprocessor_config': {
                'conf_thres': 0.25,
                'color': [0, 255, 0]
            }
        }
        
        # 尝试加载配置文件
        config_file = os.path.join(self.package_path, 'package_config.yaml')
        if os.path.exists(config_file):
            try:
                import yaml
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f)
                    config.update(file_config)
                logger.info(f"加载配置文件: {config_file}")
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
        
        return config
    
    def _should_use_base_class(self) -> bool:
        """判断是否应该使用基类版本"""
        if not self.auto_detect:
            return self.use_base_class
        
        # 自动检测基类是否可用
        try:
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            from base_classes import BaseModel, BasePostprocessor
            logger.info("检测到基类可用，使用标准版本")
            return True
        except ImportError:
            logger.info("未检测到基类，使用简化版本")
            return False
    
    def create_model(self, name: str, model_config: Optional[Dict[str, Any]] = None) -> Any:
        """
        创建模型实例
        Args:
            name: 模型名称
            model_config: 模型配置
        Returns:
            模型实例
        """
        # 合并配置
        config = self.config['model_config'].copy()
        if model_config:
            config.update(model_config)
        
        # 判断是否使用基类版本
        use_base_class = self._should_use_base_class()
        
        # 创建模型
        model = create_model(name, config, use_base_class=use_base_class)
        
        logger.info(f"创建模型: {name}, 版本: {'标准' if use_base_class else '简化'}")
        return model
    
    def create_postprocessor(self, source_id: str, alg_name: str, 
                           postprocessor_config: Optional[Dict[str, Any]] = None) -> Any:
        """
        创建后处理器实例
        Args:
            source_id: 源ID
            alg_name: 算法名称
            postprocessor_config: 后处理器配置
        Returns:
            后处理器实例
        """
        # 合并配置
        config = self.config['postprocessor_config'].copy()
        if postprocessor_config:
            config.update(postprocessor_config)
        
        # 判断是否使用基类版本
        use_base_class = self._should_use_base_class()
        
        # 创建后处理器
        postprocessor = create_postprocessor(
            source_id, alg_name, config, use_base_class=use_base_class
        )
        
        logger.info(f"创建后处理器: {alg_name}, 版本: {'标准' if use_base_class else '简化'}")
        return postprocessor
    
    def get_package_info(self) -> Dict[str, Any]:
        """获取算法包信息"""
        use_base_class = self._should_use_base_class()
        
        return {
            'name': 'YOLOv8目标检测',
            'version': '1.0.0',
            'description': '简化的YOLOv8目标检测算法包',
            'package_path': self.package_path,
            'use_base_class': use_base_class,
            'version_type': '标准版本' if use_base_class else '简化版本',
            'config': self.config
        }
    
    def validate_package(self) -> Tuple[bool, str]:
        """验证算法包"""
        try:
            # 检查模型文件
            model_file = os.path.join(
                self.package_path, 'model', 'yolov8_model', 'yolov8n.pt'
            )
            if not os.path.exists(model_file):
                return False, f"模型文件不存在: {model_file}"
            
            # 检查配置文件
            config_files = [
                os.path.join(self.package_path, 'model', 'model.yaml'),
                os.path.join(self.package_path, 'postprocessor', 'postprocessor.yaml')
            ]
            
            for config_file in config_files:
                if not os.path.exists(config_file):
                    return False, f"配置文件不存在: {config_file}"
            
            # 尝试创建模型和后处理器
            model = self.create_model('test_model')
            postprocessor = self.create_postprocessor('test_source', 'test_alg')
            
            return True, "算法包验证通过"
            
        except Exception as e:
            return False, f"算法包验证失败: {e}"


# 全局算法包管理器实例
_package_manager = None

def get_package_manager() -> AlgorithmPackageManager:
    """获取全局算法包管理器实例"""
    global _package_manager
    if _package_manager is None:
        _package_manager = AlgorithmPackageManager()
    return _package_manager

def create_algorithm_package(package_path: str = None) -> AlgorithmPackageManager:
    """创建算法包管理器"""
    return AlgorithmPackageManager(package_path) 