"""
算法包管理器
- 支持算法包的自动解压缩、校验和导入
- 统一算法包结构
- 提供算法包注册和发现功能
"""

import os
import json
import zipfile
import hashlib
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AlgorithmPackage:
    """算法包类"""
    
    def __init__(self, package_path: str):
        self.package_path = Path(package_path)
        self.package_id = self.package_path.name
        self.metadata = {}
        self.model_config = {}
        self.postprocessor_config = {}
        self._load_metadata()
    
    def _load_metadata(self):
        """加载包元数据"""
        try:
            # 检查包结构
            if not self.package_path.exists():
                raise ValueError(f"算法包不存在: {self.package_path}")
            
            # 检查必要的目录和文件
            model_dir = self.package_path / "model"
            postprocessor_dir = self.package_path / "postprocessor"
            
            if not model_dir.exists():
                raise ValueError(f"模型目录不存在: {model_dir}")
            
            if not postprocessor_dir.exists():
                raise ValueError(f"后处理目录不存在: {postprocessor_dir}")
            
            # 加载模型配置
            model_config_file = model_dir / "model.yaml"
            if model_config_file.exists():
                import yaml
                with open(model_config_file, 'r', encoding='utf-8') as f:
                    self.model_config = yaml.safe_load(f)
            
            # 加载后处理配置
            postprocessor_config_file = postprocessor_dir / "postprocessor.yaml"
            if postprocessor_config_file.exists():
                import yaml
                with open(postprocessor_config_file, 'r', encoding='utf-8') as f:
                    self.postprocessor_config = yaml.safe_load(f)
            
            # 生成元数据
            self.metadata = {
                "package_id": self.package_id,
                "name": self.postprocessor_config.get("name", self.package_id),
                "ch_name": self.postprocessor_config.get("ch_name", self.package_id),
                "description": self.postprocessor_config.get("desc", ""),
                "group_name": self.postprocessor_config.get("group_name", "目标检测"),
                "version": self.postprocessor_config.get("version", "1.0.0"),
                "process_time": self.postprocessor_config.get("process_time", 10),
                "alert_labels": self.postprocessor_config.get("alert_label", []),
                "algorithm_type": self.model_config.get("yolov8_model", {}).get("type", "unknown"),
                "installed_at": datetime.now().isoformat(),
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"加载算法包元数据失败: {e}")
            raise
    
    def get_model_module(self):
        """获取模型模块"""
        try:
            import sys
            sys.path.insert(0, str(self.package_path))
            
            # 动态导入模型模块
            model_module = __import__(f"{self.package_id}.model", fromlist=["*"])
            return model_module
        except Exception as e:
            logger.error(f"获取模型模块失败: {e}")
            raise
    
    def get_postprocessor_module(self):
        """获取后处理模块"""
        try:
            import sys
            sys.path.insert(0, str(self.package_path))
            
            # 动态导入后处理模块
            postprocessor_module = __import__(f"{self.package_id}.postprocessor", fromlist=["*"])
            return postprocessor_module
        except Exception as e:
            logger.error(f"获取后处理模块失败: {e}")
            raise
    
    def validate(self) -> Tuple[bool, str]:
        """验证算法包"""
        try:
            # 检查基本结构
            required_dirs = ["model", "postprocessor"]
            for dir_name in required_dirs:
                if not (self.package_path / dir_name).exists():
                    return False, f"缺少必要目录: {dir_name}"
            
            # 检查配置文件
            required_files = [
                "model/model.yaml",
                "postprocessor/postprocessor.yaml"
            ]
            for file_path in required_files:
                if not (self.package_path / file_path).exists():
                    return False, f"缺少必要文件: {file_path}"
            
            # 检查模型文件
            model_config = self.model_config.get("yolov8_model", {})
            model_file = model_config.get("model_file")
            if model_file:
                model_path = self.package_path / "model" / "yolov8_model" / model_file
                if not model_path.exists():
                    return False, f"模型文件不存在: {model_file}"
            
            return True, "验证通过"
            
        except Exception as e:
            return False, f"验证失败: {e}"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "package_id": self.package_id,
            "metadata": self.metadata,
            "model_config": self.model_config,
            "postprocessor_config": self.postprocessor_config,
            "package_path": str(self.package_path)
        }

class AlgorithmPackageManager:
    """算法包管理器"""
    
    def __init__(self, installed_dir: str = "algorithms/installed"):
        self.installed_dir = Path(installed_dir)
        self.packages: Dict[str, AlgorithmPackage] = {}
        self._load_installed_packages()
    
    def _load_installed_packages(self):
        """加载已安装的算法包"""
        if not self.installed_dir.exists():
            logger.warning(f"算法包安装目录不存在: {self.installed_dir}")
            return
        
        for package_dir in self.installed_dir.iterdir():
            if package_dir.is_dir() and not package_dir.name.startswith('.'):
                try:
                    package = AlgorithmPackage(str(package_dir))
                    self.packages[package.package_id] = package
                    logger.info(f"加载算法包: {package.package_id}")
                except Exception as e:
                    logger.error(f"加载算法包失败 {package_dir.name}: {e}")
    
    def install_package(self, zip_path: str) -> Tuple[bool, str, Optional[str]]:
        """安装算法包
        
        Args:
            zip_path: 算法包zip文件路径
            
        Returns:
            (成功标志, 消息, 包ID)
        """
        try:
            zip_path = Path(zip_path)
            if not zip_path.exists():
                return False, f"算法包文件不存在: {zip_path}", None
            
            # 验证zip文件
            if not zipfile.is_zipfile(zip_path):
                return False, "文件不是有效的zip格式", None
            
            # 创建安装目录
            self.installed_dir.mkdir(parents=True, exist_ok=True)
            
            # 解压算法包
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 检查zip文件结构
                file_list = zip_ref.namelist()
                if not any(name.startswith('model/') for name in file_list):
                    return False, "zip文件缺少model目录", None
                if not any(name.startswith('postprocessor/') for name in file_list):
                    return False, "zip文件缺少postprocessor目录", None
                
                # 提取包名
                package_name = None
                for name in file_list:
                    if name.startswith('model/') and name != 'model/':
                        package_name = name.split('/')[0]
                        break
                
                if not package_name:
                    return False, "无法确定包名", None
                
                # 解压到临时目录
                temp_dir = self.installed_dir / f"temp_{package_name}"
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                
                zip_ref.extractall(temp_dir)
                
                # 验证包结构
                package = AlgorithmPackage(str(temp_dir))
                is_valid, message = package.validate()
                
                if not is_valid:
                    shutil.rmtree(temp_dir)
                    return False, f"算法包验证失败: {message}", None
                
                # 移动到最终位置
                final_dir = self.installed_dir / package_name
                if final_dir.exists():
                    shutil.rmtree(final_dir)
                
                shutil.move(str(temp_dir), str(final_dir))
                
                # 重新加载包
                package = AlgorithmPackage(str(final_dir))
                self.packages[package.package_id] = package
                
                logger.info(f"算法包安装成功: {package.package_id}")
                return True, "算法包安装成功", package.package_id
                
        except Exception as e:
            logger.error(f"安装算法包失败: {e}")
            return False, f"安装失败: {e}", None
    
    def uninstall_package(self, package_id: str) -> Tuple[bool, str]:
        """卸载算法包"""
        try:
            if package_id not in self.packages:
                return False, f"算法包不存在: {package_id}"
            
            package_dir = self.installed_dir / package_id
            if package_dir.exists():
                shutil.rmtree(package_dir)
            
            del self.packages[package_id]
            logger.info(f"算法包卸载成功: {package_id}")
            return True, "算法包卸载成功"
            
        except Exception as e:
            logger.error(f"卸载算法包失败: {e}")
            return False, f"卸载失败: {e}"
    
    def get_package(self, package_id: str) -> Optional[AlgorithmPackage]:
        """获取算法包"""
        return self.packages.get(package_id)
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """列出所有算法包"""
        return [package.to_dict() for package in self.packages.values()]
    
    def get_package_metadata(self, package_id: str) -> Optional[Dict[str, Any]]:
        """获取算法包元数据"""
        package = self.get_package(package_id)
        return package.metadata if package else None
    
    def validate_package(self, package_id: str) -> Tuple[bool, str]:
        """验证算法包"""
        package = self.get_package(package_id)
        if not package:
            return False, f"算法包不存在: {package_id}"
        
        return package.validate()
    
    def get_available_algorithms(self) -> List[Dict[str, Any]]:
        """获取可用的算法列表"""
        algorithms = []
        for package in self.packages.values():
            metadata = package.metadata
            algorithms.append({
                "algorithm_id": package.package_id,
                "name": metadata.get("name", package.package_id),
                "ch_name": metadata.get("ch_name", package.package_id),
                "description": metadata.get("description", ""),
                "group_name": metadata.get("group_name", "目标检测"),
                "version": metadata.get("version", "1.0.0"),
                "algorithm_type": metadata.get("algorithm_type", "unknown"),
                "status": metadata.get("status", "active"),
                "package_id": package.package_id
            })
        return algorithms

# 全局算法包管理器实例
_package_manager = None

def get_package_manager() -> AlgorithmPackageManager:
    """获取全局算法包管理器实例"""
    global _package_manager
    if _package_manager is None:
        _package_manager = AlgorithmPackageManager()
    return _package_manager 