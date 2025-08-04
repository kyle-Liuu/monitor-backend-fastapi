"""
算法管理模块 - 重构自algorithm_manager.py
- 管理算法加载和推理
- 算法资源池管理
- 模型和后处理分离设计
"""

import os
import sys
import importlib.util
import yaml
import json
import logging
import time
import uuid
import sqlite3
import threading
from pathlib import Path
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

# 导入事件总线
from .event_bus import get_event_bus, Event

logger = logging.getLogger(__name__)

class AlgorithmModule:
    """算法管理模块，负责算法加载、推理和资源管理"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = AlgorithmModule()
            return cls._instance
    
    def __init__(self):
        """初始化算法管理器"""
        # 基本属性
        self.running = False
        self.lock = threading.RLock()
        
        # 数据库路径
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "app.db")
        
        # 模型缓存
        self.model_instances = {}  # {algo_id: model_instance}
        self.model_modules = {}    # {algo_id: model_module}
        self.model_usage_count = {}  # {algo_id: count}
        
        # 后处理器缓存
        self.postprocessor_instances = {}  # {task_id: postprocessor_instance}
        self.postprocessor_modules = {}    # {algo_id: postprocessor_module}
        
        # 事件总线
        self.event_bus = get_event_bus()
    
    def start(self):
        """启动算法模块"""
        if self.running:
            return True
        
        logger.info("启动算法管理模块")
        self.running = True
        
        # 发布模块启动事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "algorithm_module",
            {"module": "algorithm", "status": True}
        ))
        
        return True
    
    def stop(self):
        """停止算法模块"""
        if not self.running:
            return True
        
        logger.info("停止算法管理模块")
        
        # 清理所有资源
        self.cleanup_all()
        
        self.running = False
        
        # 发布模块停止事件
        self.event_bus.publish(Event(
            "module.status_changed", 
            "algorithm_module",
            {"module": "algorithm", "status": False}
        ))
        
        return True
    
    def get_algorithm_path(self, algo_id: str) -> Optional[str]:
        """获取算法路径"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询算法路径
            cursor.execute("SELECT package_name FROM algorithms WHERE algo_id = ?", (algo_id,))
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.error(f"算法不存在: {algo_id}")
                return None
            
            algo_path = result[0]
            
            # 检查路径是否为相对路径
            if not os.path.isabs(algo_path):
                # 构建完整路径，算法通常位于algorithms/installed目录下
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                algo_path = os.path.join(base_dir, "algorithms", "installed", algo_path)
            
            if not os.path.exists(algo_path):
                logger.error(f"算法路径不存在: {algo_path}")
                return None
            
            return algo_path
        except Exception as e:
            logger.error(f"获取算法路径失败: {e}")
            return None
    
    def load_model_module(self, algo_id: str) -> Tuple[Any, Optional[str]]:
        """加载算法模型模块"""
        with self.lock:
            # 检查缓存
            if algo_id in self.model_modules:
                return self.model_modules[algo_id], None
            
            try:
                # 获取算法路径
                algo_path = self.get_algorithm_path(algo_id)
                if not algo_path:
                    return None, f"算法路径不存在: {algo_id}"
                
                # 构建模型模块路径
                model_dir = os.path.join(algo_path, "model")
                model_file = os.path.join(model_dir, "simple_yolo.py")
                
                if not os.path.exists(model_file):
                    return None, f"模型文件不存在: {model_file}"
                
                # 动态加载模块
                module_name = f"algo_{algo_id}_model"
                spec = importlib.util.spec_from_file_location(module_name, model_file)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # 验证模块是否包含必要的函数
                if not hasattr(module, "create_model"):
                    return None, f"模型模块缺少create_model函数: {model_file}"
                
                # 缓存模块
                self.model_modules[algo_id] = module
                
                # 发布模块加载事件
                self.event_bus.publish(Event(
                    "algorithm.model_module_loaded",
                    "algorithm_module",
                    {"algo_id": algo_id}
                ))
                
                logger.info(f"加载模型模块成功: {algo_id}")
                return module, None
                
            except Exception as e:
                logger.error(f"加载模型模块异常: {e}")
                return None, str(e)
    
    def load_postprocessor_module(self, algo_id: str) -> Tuple[Any, Optional[str]]:
        """加载算法后处理模块"""
        with self.lock:
            # 检查缓存
            if algo_id in self.postprocessor_modules:
                return self.postprocessor_modules[algo_id], None
            
            try:
                # 获取算法路径
                algo_path = self.get_algorithm_path(algo_id)
                if not algo_path:
                    return None, f"算法路径不存在: {algo_id}"
                
                # 构建后处理模块路径
                postprocessor_dir = os.path.join(algo_path, "postprocessor")
                postprocessor_file = os.path.join(postprocessor_dir, "simple_postprocessor.py")
                
                if not os.path.exists(postprocessor_file):
                    return None, f"后处理文件不存在: {postprocessor_file}"
                
                # 动态加载模块
                module_name = f"algo_{algo_id}_postprocessor"
                spec = importlib.util.spec_from_file_location(module_name, postprocessor_file)
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # 验证模块是否包含必要的函数
                if not hasattr(module, "create_postprocessor"):
                    return None, f"后处理模块缺少create_postprocessor函数: {postprocessor_file}"
                
                # 缓存模块
                self.postprocessor_modules[algo_id] = module
                
                # 发布模块加载事件
                self.event_bus.publish(Event(
                    "algorithm.postprocessor_module_loaded",
                    "algorithm_module",
                    {"algo_id": algo_id}
                ))
                
                logger.info(f"加载后处理模块成功: {algo_id}")
                return module, None
                
            except Exception as e:
                logger.error(f"加载后处理模块异常: {e}")
                return None, str(e)
    
    def get_model_instance(self, algo_id: str, model_name: str = None, config: Dict = None) -> Tuple[Any, Optional[str]]:
        """获取模型实例
        
        Args:
            algo_id: 算法ID
            model_name: 模型名称
            config: 模型配置
        
        Returns:
            (模型实例, 错误消息)
        """
        with self.lock:
            if not self.running:
                return None, "模块未运行"
                
            # 检查缓存
            if algo_id in self.model_instances:
                # 增加使用计数
                if algo_id in self.model_usage_count:
                    self.model_usage_count[algo_id] += 1
                else:
                    self.model_usage_count[algo_id] = 1
                
                return self.model_instances[algo_id], None
            
            try:
                # 加载模型模块
                model_module, error = self.load_model_module(algo_id)
                if not model_module:
                    return None, error
                
                # 获取算法路径
                algo_path = self.get_algorithm_path(algo_id)
                if not algo_path:
                    return None, f"算法路径不存在: {algo_id}"
                
                # 构建模型目录路径
                model_dir = os.path.join(algo_path, "model")
                
                # 加载模型配置
                config_file = os.path.join(model_dir, "model.yaml")
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        default_config = yaml.safe_load(f)
                else:
                    default_config = {}
                
                # 合并配置
                if config:
                    merged_config = {**default_config, **config}
                else:
                    merged_config = default_config
                
                # 创建模型实例
                model_instance = model_module.create_model(
                    model_dir=model_dir,
                    model_name=model_name or merged_config.get("model_name", "yolov8n"),
                    config=merged_config
                )
                
                # 缓存模型实例
                self.model_instances[algo_id] = model_instance
                self.model_usage_count[algo_id] = 1
                
                # 发布模型创建事件
                self.event_bus.publish(Event(
                    "algorithm.model_created",
                    "algorithm_module",
                    {
                        "algo_id": algo_id,
                        "model_name": model_name or merged_config.get("model_name", "yolov8n")
                    }
                ))
                
                logger.info(f"创建模型实例成功: {algo_id}")
                return model_instance, None
                
            except Exception as e:
                logger.error(f"创建模型实例异常: {e}")
                return None, str(e)
    
    def get_postprocessor_instance(self, task_id: str, algo_id: str, stream_id: str, config: Dict = None) -> Tuple[Any, Optional[str]]:
        """获取后处理器实例
        
        Args:
            task_id: 任务ID
            algo_id: 算法ID
            stream_id: 流ID
            config: 后处理配置
        
        Returns:
            (后处理器实例, 错误消息)
        """
        with self.lock:
            if not self.running:
                return None, "模块未运行"
                
            # 检查缓存
            if task_id in self.postprocessor_instances:
                return self.postprocessor_instances[task_id], None
            
            try:
                # 加载后处理模块
                postprocessor_module, error = self.load_postprocessor_module(algo_id)
                if not postprocessor_module:
                    return None, error
                
                # 获取算法路径
                algo_path = self.get_algorithm_path(algo_id)
                if not algo_path:
                    return None, f"算法路径不存在: {algo_id}"
                
                # 构建后处理目录路径
                postprocessor_dir = os.path.join(algo_path, "postprocessor")
                
                # 加载后处理配置
                config_file = os.path.join(postprocessor_dir, "postprocessor.yaml")
                if os.path.exists(config_file):
                    with open(config_file, 'r') as f:
                        default_config = yaml.safe_load(f)
                else:
                    default_config = {}
                
                # 合并配置
                if config:
                    merged_config = {**default_config, **config}
                else:
                    merged_config = default_config
                
                # 创建后处理器实例
                postprocessor_instance = postprocessor_module.create_postprocessor(
                    config_dir=postprocessor_dir,
                    stream_id=stream_id,
                    task_id=task_id,
                    config=merged_config
                )
                
                # 缓存后处理器实例
                self.postprocessor_instances[task_id] = postprocessor_instance
                
                # 发布后处理器创建事件
                self.event_bus.publish(Event(
                    "algorithm.postprocessor_created",
                    "algorithm_module",
                    {
                        "task_id": task_id,
                        "algo_id": algo_id,
                        "stream_id": stream_id
                    }
                ))
                
                logger.info(f"创建后处理器实例成功: {task_id}/{algo_id}")
                return postprocessor_instance, None
                
            except Exception as e:
                logger.error(f"创建后处理器实例异常: {e}")
                return None, str(e)
    
    def run_inference(self, task_id: str, algo_id: str, stream_id: str, images: List[np.ndarray], params: Dict = None) -> Tuple[Dict, Optional[str]]:
        """执行推理
        
        Args:
            task_id: 任务ID
            algo_id: 算法ID
            stream_id: 流ID
            images: 图像列表
            params: 推理参数
            
        Returns:
            (推理结果, 错误消息)
        """
        if not self.running:
            return None, "模块未运行"
            
        try:
            # 获取模型实例
            model, error = self.get_model_instance(algo_id)
            if not model:
                return None, error
            
            # 获取后处理器实例
            postprocessor, error = self.get_postprocessor_instance(task_id, algo_id, stream_id)
            if not postprocessor:
                return None, error
            
            # 执行推理
            start_time = time.time()
            
            # 执行模型推理
            if hasattr(model, "predict_batch"):
                # 批量推理
                model_outputs = model.predict_batch(images)
            else:
                # 逐帧推理
                model_outputs = []
                for image in images:
                    output = model.predict(image)
                    model_outputs.append(output)
            
            # 执行后处理
            if hasattr(postprocessor, "process_batch"):
                # 批量后处理
                results = postprocessor.process_batch(model_outputs, images, params or {})
            else:
                # 逐帧后处理
                results = []
                for i, output in enumerate(model_outputs):
                    result = postprocessor.process(output, images[i], params or {})
                    results.append(result)
            
            # 计算推理时间
            inference_time = time.time() - start_time
            
            # 构建结果
            final_result = {
                "task_id": task_id,
                "algo_id": algo_id,
                "stream_id": stream_id,
                "results": results,
                "inference_time": inference_time,
                "timestamp": time.time(),
                "image_count": len(images)
            }
            
            # 发布推理完成事件
            self.event_bus.publish(Event(
                "algorithm.inference_completed",
                "algorithm_module",
                {
                    "task_id": task_id,
                    "algo_id": algo_id,
                    "stream_id": stream_id,
                    "inference_time": inference_time,
                    "image_count": len(images)
                }
            ))
            
            return final_result, None
            
        except Exception as e:
            logger.error(f"执行推理异常: {task_id}/{algo_id}, {e}")
            
            # 发布推理错误事件
            self.event_bus.publish(Event(
                "algorithm.inference_error",
                "algorithm_module",
                {
                    "task_id": task_id,
                    "algo_id": algo_id,
                    "stream_id": stream_id,
                    "error": str(e)
                }
            ))
            
            return None, str(e)
    
    def cleanup_model(self, algo_id: str) -> Optional[str]:
        """清理模型资源"""
        with self.lock:
            try:
                # 减少使用计数
                if algo_id in self.model_usage_count:
                    self.model_usage_count[algo_id] -= 1
                    
                    # 如果仍有使用，不清理
                    if self.model_usage_count[algo_id] > 0:
                        return None
                
                # 清理模型实例
                if algo_id in self.model_instances:
                    model_instance = self.model_instances[algo_id]
                    
                    # 调用清理方法（如果存在）
                    if hasattr(model_instance, "cleanup"):
                        model_instance.cleanup()
                    
                    # 移除缓存
                    del self.model_instances[algo_id]
                    
                    # 移除使用计数
                    if algo_id in self.model_usage_count:
                        del self.model_usage_count[algo_id]
                    
                    logger.info(f"清理模型实例: {algo_id}")
                
                return None
                
            except Exception as e:
                logger.error(f"清理模型异常: {e}")
                return str(e)
    
    def cleanup_processor(self, task_id: str) -> Optional[str]:
        """清理后处理器资源"""
        with self.lock:
            try:
                # 清理后处理器实例
                if task_id in self.postprocessor_instances:
                    postprocessor = self.postprocessor_instances[task_id]
                    
                    # 调用清理方法（如果存在）
                    if hasattr(postprocessor, "cleanup"):
                        postprocessor.cleanup()
                    
                    # 移除缓存
                    del self.postprocessor_instances[task_id]
                    
                    logger.info(f"清理后处理器实例: {task_id}")
                
                return None
                
            except Exception as e:
                logger.error(f"清理后处理器异常: {e}")
                return str(e)
    
    def cleanup_task(self, task_id: str, algo_id: str) -> Optional[str]:
        """清理任务相关资源"""
        with self.lock:
            try:
                # 清理后处理器
                error = self.cleanup_processor(task_id)
                if error:
                    return error
                
                # 清理模型
                error = self.cleanup_model(algo_id)
                if error:
                    return error
                
                # 发布清理完成事件
                self.event_bus.publish(Event(
                    "algorithm.task_cleaned",
                    "algorithm_module",
                    {
                        "task_id": task_id,
                        "algo_id": algo_id
                    }
                ))
                
                return None
                
            except Exception as e:
                logger.error(f"清理任务资源异常: {e}")
                return str(e)
    
    def cleanup_all(self) -> None:
        """清理所有资源"""
        with self.lock:
            logger.info("清理所有算法资源")
            
            # 清理所有后处理器
            for task_id in list(self.postprocessor_instances.keys()):
                self.cleanup_processor(task_id)
            
            # 清理所有模型
            for algo_id in list(self.model_instances.keys()):
                self.cleanup_model(algo_id)
            
            # 清空模块缓存
            self.model_modules = {}
            self.postprocessor_modules = {}
            
            # 发布清理完成事件
            self.event_bus.publish(Event(
                "algorithm.all_cleaned",
                "algorithm_module",
                {}
            ))
    
    def get_algorithm_info(self, algo_id: str = None) -> Dict:
        """获取算法信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if algo_id:
                # 获取特定算法信息
                cursor.execute(
                    """
                    SELECT algo_id, name, version, description, package_name, 
                    created_at, updated_at, author, algorithm_type, status, device_type
                    FROM algorithms WHERE algo_id = ?
                    """, 
                    (algo_id,)
                )
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    return {}
                
                # 处理device_type字段，确保返回字符串格式
                device_type = result[10] if result[10] else "cpu,gpu"
                
                return {
                    "algo_id": result[0],
                    "name": result[1],
                    "version": result[2],
                    "description": result[3],
                    "package_name": result[4],
                    "created_at": result[5],
                    "updated_at": result[6],
                    "author": result[7],
                    "algorithm_type": result[8],
                    "status": result[9],
                    "device_type": device_type,
                    "is_loaded": algo_id in self.model_instances
                }
            else:
                # 获取所有算法信息
                cursor.execute(
                    """
                    SELECT algo_id, name, version, description, package_name, 
                    created_at, updated_at, author, algorithm_type, status, device_type
                    FROM algorithms
                    """
                )
                results = cursor.fetchall()
                conn.close()
                
                algorithms = {}
                for row in results:
                    algo_id = row[0]
                    
                    # 处理device_type字段，确保返回字符串格式
                    device_type = row[10] if row[10] else "cpu,gpu"
                    
                    algorithms[algo_id] = {
                        "algo_id": row[0],
                        "name": row[1],
                        "version": row[2],
                        "description": row[3],
                        "package_name": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                        "author": row[7],
                        "algorithm_type": row[8],
                        "status": row[9],
                        "device_type": device_type,
                        "is_loaded": algo_id in self.model_instances
                    }
                
                return algorithms
                
        except Exception as e:
            logger.error(f"获取算法信息异常: {e}")
            return {}

# 全局算法管理模块实例
def get_algorithm_module():
    """获取全局算法管理模块实例"""
    return AlgorithmModule.get_instance() 