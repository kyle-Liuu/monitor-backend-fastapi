"""
算法包统一基类
- 定义标准的模型和后处理器接口
- 提供统一的算法包结构规范
- 支持自动解压缩、校验和导入
"""

import abc
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import yaml
import json
import threading

logger = logging.getLogger(__name__)

class BaseModel(abc.ABC):
    """模型基类 - 所有算法模型必须继承此类"""
    
    def __init__(self, model_config: Dict[str, Any]):
        """
        初始化模型
        Args:
            model_config: 模型配置字典
        """
        self.config = model_config
        self.model = None
        self.device = self._get_device()
        self.is_warmed_up = False
        self._load_model()
    
    @abc.abstractmethod
    def _load_model(self):
        """加载模型 - 子类必须实现"""
        pass
    
    @abc.abstractmethod
    def _warmup(self):
        """模型预热 - 子类必须实现"""
        pass
    
    @abc.abstractmethod
    def infer(self, image: np.ndarray) -> Tuple[Any, List[Dict]]:
        """
        执行推理
        Args:
            image: 输入图像 (BGR格式)
        Returns:
            Tuple[原始结果, 标准化结果列表]
        """
        pass
    
    def warmup(self):
        """执行模型预热"""
        if not self.is_warmed_up:
            self._warmup()
            self.is_warmed_up = True
            logger.info(f"模型预热完成: {self.__class__.__name__}")
    
    def _get_device(self) -> str:
        """获取计算设备"""
        try:
            import torch
            return 'cuda:0' if torch.cuda.is_available() else 'cpu'
        except ImportError:
            return 'cpu'
    
    def release(self):
        """释放模型资源"""
        if self.model is not None:
            del self.model
            self.model = None
        logger.info(f"模型资源已释放: {self.__class__.__name__}")


class BasePostprocessor(abc.ABC):
    """后处理器基类 - 所有算法后处理器必须继承此类"""
    
    def __init__(self, postprocessor_config: Dict[str, Any]):
        """
        初始化后处理器
        Args:
            postprocessor_config: 后处理器配置字典
        """
        self.config = postprocessor_config
        self.conf_threshold = postprocessor_config.get('conf_threshold', 0.25)
        self.label_whitelist = postprocessor_config.get('label_whitelist', None)
        self.color = postprocessor_config.get('color', [0, 255, 0])
    
    @abc.abstractmethod
    def process(self, model_results: List[Dict], image_shape: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        处理后处理
        Args:
            model_results: 模型推理结果列表
            image_shape: 图像尺寸 (height, width)
        Returns:
            标准化的后处理结果
        """
        pass
    
    def filter_results(self, results: List[Dict]) -> List[Dict]:
        """过滤结果"""
        filtered = []
        for result in results:
            conf = result.get('conf', 0)
            label = result.get('label', -1)
            
            if conf >= self.conf_threshold:
                if self.label_whitelist is None or label in self.label_whitelist:
                    filtered.append(result)
        
        return filtered


class BaseAlgorithmPackage:
    """算法包基类 - 定义标准算法包结构"""
    
    def __init__(self, package_path: str):
        """
        初始化算法包
        Args:
            package_path: 算法包路径
        """
        self.package_path = Path(package_path)
        self.package_id = self.package_path.name
        self.model_config = {}
        self.postprocessor_config = {}
        self.metadata = {}
        self._load_configs()
    
    def _load_configs(self):
        """加载配置文件"""
        # 加载模型配置
        model_config_file = self.package_path / "model" / "model.yaml"
        if model_config_file.exists():
            with open(model_config_file, 'r', encoding='utf-8') as f:
                self.model_config = yaml.safe_load(f)
        
        # 加载后处理器配置
        postprocessor_config_file = self.package_path / "postprocessor" / "postprocessor.yaml"
        if postprocessor_config_file.exists():
            with open(postprocessor_config_file, 'r', encoding='utf-8') as f:
                self.postprocessor_config = yaml.safe_load(f)
        
        # 生成元数据
        self._generate_metadata()
    
    def _generate_metadata(self):
        """生成包元数据"""
        self.metadata = {
            "package_id": self.package_id,
            "name": self.postprocessor_config.get("name", self.package_id),
            "description": self.postprocessor_config.get("description", ""),
            "version": self.postprocessor_config.get("version", "1.0.0"),
            "algorithm_type": self.model_config.get("algorithm_type", "unknown"),
            "device_type": self.model_config.get("device_type", "cpu,gpu"),
            "input_format": self.model_config.get("input_format", "BGR"),
            "output_format": self.postprocessor_config.get("output_format", "standard"),
        }
    
    @abc.abstractmethod
    def create_model(self, model_config: Dict[str, Any]) -> BaseModel:
        """创建模型实例"""
        pass
    
    @abc.abstractmethod
    def create_postprocessor(self, postprocessor_config: Dict[str, Any]) -> BasePostprocessor:
        """创建后处理器实例"""
        pass
    
    def validate(self) -> Tuple[bool, str]:
        """验证算法包"""
        try:
            # 检查必要文件
            required_files = [
                "model/model.yaml",
                "postprocessor/postprocessor.yaml",
                "model/__init__.py",
                "postprocessor/__init__.py"
            ]
            
            for file_path in required_files:
                if not (self.package_path / file_path).exists():
                    return False, f"缺少必要文件: {file_path}"
            
            # 检查模型文件
            model_file = self.model_config.get("model_file")
            if model_file:
                model_path = self.package_path / "model" / model_file
                if not model_path.exists():
                    return False, f"模型文件不存在: {model_file}"
            
            return True, "验证通过"
            
        except Exception as e:
            return False, f"验证失败: {str(e)}"


class ModelInstanceManager:
    """模型实例管理器 - 负责模型实例的创建、预热和复用"""
    
    def __init__(self):
        self.instances = {}  # {instance_id: model_instance}
        self.instance_configs = {}  # {instance_id: config}
        self.instance_status = {}  # {instance_id: status}
        self.instance_usage_count = {}  # {instance_id: usage_count}
        self.lock = threading.RLock()
    
    def create_instance(self, instance_id: str, model: BaseModel, config: Dict[str, Any]) -> bool:
        """
        创建模型实例
        Args:
            instance_id: 实例ID
            model: 模型对象
            config: 实例配置
        Returns:
            是否创建成功
        """
        with self.lock:
            try:
                # 预热模型
                model.warmup()
                
                # 保存实例
                self.instances[instance_id] = model
                self.instance_configs[instance_id] = config
                self.instance_status[instance_id] = "idle"
                self.instance_usage_count[instance_id] = 0
                
                logger.info(f"模型实例创建成功: {instance_id}")
                return True
                
            except Exception as e:
                logger.error(f"创建模型实例失败: {e}")
                return False
    
    def get_instance(self, instance_id: str) -> Optional[BaseModel]:
        """获取模型实例"""
        with self.lock:
            return self.instances.get(instance_id)
    
    def use_instance(self, instance_id: str) -> bool:
        """使用模型实例"""
        with self.lock:
            if instance_id in self.instances:
                self.instance_status[instance_id] = "busy"
                self.instance_usage_count[instance_id] += 1
                return True
            return False
    
    def release_instance(self, instance_id: str):
        """释放模型实例"""
        with self.lock:
            if instance_id in self.instances:
                self.instance_status[instance_id] = "idle"
    
    def remove_instance(self, instance_id: str):
        """移除模型实例"""
        with self.lock:
            if instance_id in self.instances:
                # 释放模型资源
                model = self.instances[instance_id]
                model.release()
                
                # 清理记录
                del self.instances[instance_id]
                del self.instance_configs[instance_id]
                del self.instance_status[instance_id]
                del self.instance_usage_count[instance_id]
                
                logger.info(f"模型实例已移除: {instance_id}")
    
    def get_instance_status(self, instance_id: str) -> Optional[str]:
        """获取实例状态"""
        with self.lock:
            return self.instance_status.get(instance_id)
    
    def get_instance_info(self, instance_id: str) -> Optional[Dict[str, Any]]:
        """获取实例信息"""
        with self.lock:
            if instance_id not in self.instances:
                return None
            
            return {
                "instance_id": instance_id,
                "status": self.instance_status[instance_id],
                "usage_count": self.instance_usage_count[instance_id],
                "config": self.instance_configs[instance_id]
            }


# 全局模型实例管理器
_model_instance_manager = ModelInstanceManager()

def get_model_instance_manager() -> ModelInstanceManager:
    """获取全局模型实例管理器"""
    return _model_instance_manager 