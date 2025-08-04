"""
模型管理模块
- 模型注册/加载/卸载接口风格统一
- 支持多算法、多实例池，自动轮询分配
- 负载均衡策略清晰
- 只保留分析器主线相关内容
- 注释和结构一目了然
"""

import multiprocessing as mp
import logging
import time
import importlib.util
import json
import os
import sys
import threading

logger = logging.getLogger(__name__)

# 全局字典用于存储模型实例，避免跨进程传递
_model_instances = {}
_postproc_instances = {}
_model_locks = {}

class ModelRegistry:
    """模型注册表，管理所有已加载的模型"""
    
    def __init__(self):
        self.manager = mp.Manager()
        self.models = self.manager.dict()  # 存储模型配置和状态
        self.model_locks = {}
        self.model_usage = self.manager.dict()
        # 新增：实例池
        self.instance_pools = {}  # model_id: [实例, ...]
        self.instance_index = {}  # model_id: 轮询索引
        
    def register_model(self, algo_package, model_name, model_config):
        """注册模型配置"""
        model_id = f"{algo_package}_{model_name}"
        
        if model_id not in self.models:
            self.models[model_id] = {
                'package': algo_package,
                'name': model_name,
                'config': model_config,
                'status': 'unloaded',  # 未加载
                'error': None  # 错误信息
            }
            
            self.model_locks[model_id] = mp.Lock()
            self.model_usage[model_id] = {
                'total_calls': 0,
                'last_used': 0
            }
            self.instance_pools[model_id] = []
            self.instance_index[model_id] = 0
            
            # 初始化全局锁
            global _model_locks
            _model_locks[model_id] = threading.RLock()
            
            logger.info(f"已注册模型: {model_id}")
        
        return model_id
    
    def load_model(self, model_id, num_instances=1):
        """加载模型实例"""
        if model_id not in self.models:
            logger.error(f"模型未注册: {model_id}")
            return False
            
        with self.model_locks[model_id]:
            model_info = self.models[model_id]
            
            if model_info['status'] == 'loaded':
                logger.info(f"模型已加载: {model_id}")
                return True
                
            try:
                # 导入模型模块
                algo_package = model_info['package']
                model_module_path = f"{algo_package}.model.simple_yolo"
                model_spec = importlib.util.find_spec(model_module_path)
                
                if model_spec is None:
                    raise ImportError(f"无法找到算法包: {model_module_path}")
                
                model_module = importlib.util.module_from_spec(model_spec)
                model_spec.loader.exec_module(model_module)
                
                # 导入后处理模块
                postproc_module_path = f"{algo_package}.postprocessor.simple_postprocessor"
                postproc_spec = importlib.util.find_spec(postproc_module_path)
                
                if postproc_spec is None:
                    raise ImportError(f"无法找到后处理模块: {postproc_module_path}")
                
                postproc_module = importlib.util.module_from_spec(postproc_spec)
                postproc_spec.loader.exec_module(postproc_module)
                
                # 新增：扩容实例池
                if model_id not in self.instance_pools:
                    self.instance_pools[model_id] = []
                pool = self.instance_pools[model_id]
                for i in range(num_instances):
                    instance = model_module.create_model(
                        model_info['name'], 
                        model_info['config']
                    )
                    postproc_instance = postproc_module.create_postprocessor(
                        "stream_1", 
                        model_info['name'], 
                        {}
                    )
                    pool.append((instance, postproc_instance))
                
                # 更新模型信息 - 只存储状态，不存储实际实例
                self.models[model_id] = {
                    'package': algo_package,
                    'name': model_info['name'],
                    'config': model_info['config'],
                    'status': 'loaded',
                    'error': None,
                    'instance_count': len(pool)
                }
                
                logger.info(f"模型加载成功: {model_id}，实例池大小: {len(pool)}")
                return True
                
            except Exception as e:
                logger.error(f"模型加载失败: {model_id}, 错误: {e}", exc_info=True)
                
                self.models[model_id] = {
                    'package': model_info['package'],
                    'name': model_info['name'],
                    'config': model_info['config'],
                    'status': 'error',
                    'error': str(e)
                }
                
                return False
    
    def get_model_instance(self, model_id):
        """获取模型实例（负载均衡）"""
        if model_id not in self.models:
            logger.error(f"模型未注册: {model_id}")
            return None, None
            
        model_info = self.models[model_id]
        
        if model_info['status'] != 'loaded':
            logger.error(f"模型未成功加载: {model_id}")
            return None, None
        
        # 获取全局模型实例和后处理器
        global _model_instances, _postproc_instances, _model_locks
        
        # 使用线程安全的方式获取模型实例
        with _model_locks[model_id]:
            # 更新使用情况
            self.model_usage[model_id]['total_calls'] += 1
            self.model_usage[model_id]['last_used'] = time.time()
            
            # 获取实例池
            pool = self.instance_pools.get(model_id, [])
            if not pool:
                logger.error(f"模型实例池为空: {model_id}")
                return None, None
                
            # 轮询分配实例
            idx = self.instance_index.get(model_id, 0)
            instance, postproc = pool[idx % len(pool)]
            self.instance_index[model_id] = (idx + 1) % len(pool)
            
            return instance, postproc
    
    def unload_model(self, model_id):
        """卸载模型"""
        if model_id not in self.models:
            return False
            
        with self.model_locks[model_id]:
            model_info = self.models[model_id]
            
            if model_info['status'] == 'loaded':
                try:
                    global _model_instances, _postproc_instances, _model_locks
                    
                    # 释放模型实例
                    pool = self.instance_pools.get(model_id, [])
                    for instance, postproc in pool:
                        if hasattr(instance, 'release'):
                            instance.release()
                    self.instance_pools[model_id] = []
                    
                    # 清理后处理器
                    if model_id in _postproc_instances:
                        del _postproc_instances[model_id]
                    
                    # 更新状态
                    self.models[model_id] = {
                        'package': model_info['package'],
                        'name': model_info['name'],
                        'config': model_info['config'],
                        'status': 'unloaded',
                        'error': None
                    }
                    
                    logger.info(f"模型卸载成功: {model_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"模型卸载失败: {model_id}, 错误: {e}")
                    return False
            
            return True  # 已经是未加载状态 