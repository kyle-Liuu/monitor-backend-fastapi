"""
分析器服务模块 - 协调各个模块的核心服务
- 实现视频流复用和模型实例共享
- 支持算法和视频流的多对多关系
- 自动均衡分配模型实例
- 集成进程管理器支持
"""

import threading
import time
import logging
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# 添加核心模块路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from core.process_manager import ProcessManager

# 导入各个模块
from .stream_module import get_stream_module
from .algorithm_module import get_algorithm_module
from .task_module import get_task_module
from .event_bus import get_event_bus, Event
from .utils.id_generator import generate_unique_id

logger = logging.getLogger(__name__)

class AnalyzerService:
    """分析器服务，协调各个模块的核心服务"""
    
    _instance = None  # 单例模式
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = AnalyzerService()
            return cls._instance
    
    def __init__(self):
        """初始化分析器服务"""
        # 基本属性
        self.running = False
        self.lock = threading.RLock()
        
        # 获取各个模块实例
        self.stream_module = get_stream_module()
        self.algorithm_module = get_algorithm_module()
        self.task_module = get_task_module()
        self.event_bus = get_event_bus()
        
        # 进程管理器（从service.py合并）
        self.process_manager = ProcessManager()
        
        # 模型实例池管理
        self.model_pools = {}  # {algo_id: [model_instances]}
        self.model_usage = {}  # {algo_id: {model_id: usage_count}}
        self.max_instances_per_algo = 3  # 每个算法最大实例数
        
        # 流复用管理
        self.stream_consumers = {}  # {stream_id: [consumer_ids]}
        self.consumer_tasks = {}    # {consumer_id: task_id}
        
        # 任务执行状态
        self.active_tasks = {}  # {task_id: task_info}
        
        # 模块状态追踪（从service.py合并）
        self.modules_status = {
            "stream": False,
            "algorithm": False,
            "task": False,
            "alarm": False,
            "output": False
        }
        
        # 监控线程
        self.monitor_thread = None
        self.monitor_interval = 30  # 秒
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def start(self) -> bool:
        """启动分析器服务"""
        if self.running:
            return True
        
        logger.info("启动分析器服务")
        
        try:
            # 启动事件总线
            self.event_bus.start()
            
            # 初始化进程管理器
            self.process_manager.initialize()
            
            # 启动各个模块
            if not self.stream_module.start():
                logger.error("启动流模块失败")
                return False
            
            if not self.algorithm_module.start():
                logger.error("启动算法模块失败")
                return False
            
            if not self.task_module.start():
                logger.error("启动任务模块失败")
                return False
            
            self.running = True
            
            # 启动监控线程
            self.monitor_thread = threading.Thread(
                target=self._monitor_worker,
                daemon=True
            )
            self.monitor_thread.start()
            
            # 发布服务启动事件
            self.event_bus.publish(Event(
                "analyzer.service_started",
                "analyzer_service",
                {"timestamp": time.time()}
            ))
            
            logger.info("分析器服务启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动分析器服务异常: {e}")
            return False
    
    def stop(self) -> bool:
        """停止分析器服务"""
        if not self.running:
            return True
        
        logger.info("停止分析器服务")
        
        try:
            # 停止所有任务
            self._stop_all_tasks()
            
            # 停止各个模块
            self.task_module.stop()
            self.algorithm_module.stop()
            self.stream_module.stop()
            
            # 关闭进程管理器
            self.process_manager.shutdown()
            
            # 停止事件总线
            self.event_bus.stop()
            
            self.running = False
            
            # 发布服务停止事件
            self.event_bus.publish(Event(
                "analyzer.service_stopped",
                "analyzer_service",
                {"timestamp": time.time()}
            ))
            
            logger.info("分析器服务停止成功")
            return True
            
        except Exception as e:
            logger.error(f"停止分析器服务异常: {e}")
            return False
    
    def is_running(self) -> bool:
        """检查服务是否运行"""
        return self.running
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        if not self.running:
            return {"status": "stopped"}
        
        try:
            # 获取进程管理器状态
            pm_status = self.process_manager.get_status()
            
            # 构建完整状态
            status = {
                "status": "running",
                "streams": len(self.stream_module.get_stream_info()),
                "algorithms": len(self.algorithm_module.get_algorithm_info()),
                "tasks": len(self.task_module.get_task_info()),
                "active_tasks": len(self.active_tasks),
                "model_pools": {algo_id: len(instances) for algo_id, instances in self.model_pools.items()},
                "modules": self.modules_status,
                "processes": pm_status,
                "timestamp": time.time()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"获取状态异常: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    # 从service.py合并的方法
    def create_task_with_process_manager(self, task_config: Dict) -> Tuple[bool, str, Optional[str]]:
        """使用进程管理器创建新的视频分析任务
        
        Args:
            task_config: 任务配置，包含以下字段:
                - stream_id: 视频流ID
                - stream_url: 视频流URL
                - algo_id: 算法ID
                - algo_package: 算法包名
                - model_name: 模型名称
                - model_config: 模型配置
                - enable_output: 是否启用输出
                - output_url: 输出URL (可选)
        
        Returns:
            (成功标志, 消息, 任务ID)
        """
        if not self.running:
            return False, "服务未运行", None
        
        try:
            # 发布任务创建事件
            self.event_bus.publish(
                Event("task.creating", "analyzer_service", task_config)
            )
            
            # 调用进程管理器创建任务
            success, message, task_id = self._create_task_impl(task_config)
            
            if success:
                # 发布任务创建成功事件
                self.event_bus.publish(
                    Event("task.created", "analyzer_service", {
                        "task_id": task_id,
                        "config": task_config
                    })
                )
            
            return success, message, task_id
            
        except Exception as e:
            logger.error(f"创建任务异常: {e}", exc_info=True)
            return False, f"创建任务失败: {str(e)}", None
    
    def _create_task_impl(self, task_config: Dict) -> Tuple[bool, str, Optional[str]]:
        """任务创建实现"""
        # 提取必要参数
        task_id = task_config.get("task_id")
        stream_id = task_config.get("stream_id")
        stream_url = task_config.get("stream_url")
        algo_id = task_config.get("algo_id")
        algo_package = task_config.get("algo_package")
        model_name = task_config.get("model_name")
        model_config = task_config.get("model_config", {})
        enable_output = task_config.get("enable_output", True)
        output_url = task_config.get("output_url")
        
        # 检查必要参数
        if not all([stream_id, stream_url, algo_id, algo_package]):
            return False, "缺少必要参数", None
        
        # 调用进程管理器创建任务
        success, message = self.process_manager.create_task(
            task_id or f"task_{stream_id}_{algo_id}",
            stream_id, stream_url, algo_id, algo_package,
            model_name, model_config, output_url, enable_output
        )
        
        if not success:
            return False, message, None
            
        return True, "任务创建成功", task_id or f"task_{stream_id}_{algo_id}"
    
    def stop_task_with_process_manager(self, task_id: str) -> Tuple[bool, str]:
        """使用进程管理器停止任务"""
        if not self.running:
            return False, "服务未运行"
        
        try:
            # 解析任务ID获取stream_id和algo_id
            # 假设任务ID格式为 task_stream_id_algo_id
            parts = task_id.split('_')
            if len(parts) >= 3:
                stream_id = parts[1]
                algo_id = parts[2]
            else:
                return False, "无效的任务ID格式"
            
            # 发布任务停止事件
            self.event_bus.publish(
                Event("task.stopping", "analyzer_service", {
                    "task_id": task_id,
                    "stream_id": stream_id,
                    "algo_id": algo_id
                })
            )
            
            # 调用进程管理器停止任务
            success, message = self.process_manager.stop_task(stream_id, algo_id)
            
            if success:
                # 发布任务停止成功事件
                self.event_bus.publish(
                    Event("task.stopped", "analyzer_service", {
                        "task_id": task_id,
                        "stream_id": stream_id,
                        "algo_id": algo_id
                    })
                )
            
            return success, message
            
        except Exception as e:
            logger.error(f"停止任务异常: {e}", exc_info=True)
            return False, f"停止任务失败: {str(e)}"
    
    # 原有的模块级任务管理方法
    def create_task(self, stream_id: str, algorithm_id: str, name: str = None,
                   description: str = "", config: Dict = None, alarm_config: Dict = None) -> Tuple[bool, str, Optional[str]]:
        """创建分析任务"""
        if not self.running:
            return False, "服务未运行", None
        
        with self.lock:
            try:
                # 创建任务
                success, error, task_id = self.task_module.create_task(
                    stream_id=stream_id,
                    algorithm_id=algorithm_id,
                    name=name,
                    description=description,
                    config=config,
                    alarm_config=alarm_config
                )
                
                if not success:
                    return False, error, None
                
                # 确保流已启动
                stream_info = self.stream_module.get_stream_info(stream_id)
                if not stream_info:
                    return False, f"流不存在: {stream_id}", None
                
                # 确保算法可用
                algo_info = self.algorithm_module.get_algorithm_info(algorithm_id)
                if not algo_info:
                    return False, f"算法不存在: {algorithm_id}", None
                
                # 初始化模型实例池（如果需要）
                self._ensure_model_pool(algorithm_id)
                
                # 添加为流的消费者
                consumer_id = f"task_{task_id}"
                if self.stream_module.add_consumer(stream_id, consumer_id):
                    self.stream_consumers.setdefault(stream_id, []).append(consumer_id)
                    self.consumer_tasks[consumer_id] = task_id
                
                # 记录活动任务
                self.active_tasks[task_id] = {
                    "task_id": task_id,
                    "stream_id": stream_id,
                    "algorithm_id": algorithm_id,
                    "status": "created",
                    "created_at": time.time()
                }
                
                logger.info(f"创建分析任务成功: {task_id}")
                return True, "任务创建成功", task_id
                
            except Exception as e:
                logger.error(f"创建分析任务异常: {e}")
                return False, str(e), None
    
    def start_task(self, task_id: str) -> Tuple[bool, str]:
        """启动分析任务"""
        if not self.running:
            return False, "服务未运行"
        
        with self.lock:
            try:
                # 检查任务是否存在
                if task_id not in self.active_tasks:
                    return False, f"任务不存在: {task_id}"
                
                # 启动任务
                success, error = self.task_module.start_task(task_id)
                if not success:
                    return False, error
                
                # 更新活动任务状态
                self.active_tasks[task_id]["status"] = "running"
                self.active_tasks[task_id]["started_at"] = time.time()
                
                logger.info(f"启动分析任务成功: {task_id}")
                return True, "任务启动成功"
                
            except Exception as e:
                logger.error(f"启动分析任务异常: {e}")
                return False, str(e)
    
    def stop_task(self, task_id: str) -> Tuple[bool, str]:
        """停止分析任务"""
        if not self.running:
            return False, "服务未运行"
        
        with self.lock:
            try:
                # 检查任务是否存在
                if task_id not in self.active_tasks:
                    return False, f"任务不存在: {task_id}"
                
                # 停止任务
                success, error = self.task_module.stop_task(task_id)
                if not success:
                    return False, error
                
                # 更新活动任务状态
                self.active_tasks[task_id]["status"] = "stopped"
                self.active_tasks[task_id]["stopped_at"] = time.time()
                
                logger.info(f"停止分析任务成功: {task_id}")
                return True, "任务停止成功"
                
            except Exception as e:
                logger.error(f"停止分析任务异常: {e}")
                return False, str(e)
    
    def delete_task(self, task_id: str) -> Tuple[bool, str]:
        """删除分析任务"""
        if not self.running:
            return False, "服务未运行"
        
        with self.lock:
            try:
                # 检查任务是否存在
                if task_id not in self.active_tasks:
                    return False, f"任务不存在: {task_id}"
                
                task_info = self.active_tasks[task_id]
                stream_id = task_info["stream_id"]
                
                # 删除任务
                success, error = self.task_module.delete_task(task_id)
                if not success:
                    return False, error
                
                # 移除流消费者
                consumer_id = f"task_{task_id}"
                if consumer_id in self.consumer_tasks:
                    del self.consumer_tasks[consumer_id]
                
                if stream_id in self.stream_consumers:
                    if consumer_id in self.stream_consumers[stream_id]:
                        self.stream_consumers[stream_id].remove(consumer_id)
                        self.stream_module.remove_consumer(stream_id, consumer_id)
                
                # 移除活动任务
                del self.active_tasks[task_id]
                
                logger.info(f"删除分析任务成功: {task_id}")
                return True, "任务删除成功"
                
            except Exception as e:
                logger.error(f"删除分析任务异常: {e}")
                return False, str(e)
    
    def get_task_status(self) -> Dict[str, Any]:
        """获取任务状态"""
        if not self.running:
            return {}
        
        return {
            "total_tasks": len(self.active_tasks),
            "running_tasks": len([t for t in self.active_tasks.values() if t["status"] == "running"]),
            "stopped_tasks": len([t for t in self.active_tasks.values() if t["status"] == "stopped"]),
            "tasks": list(self.active_tasks.values())
        }
    
    def get_model_instance(self, algorithm_id: str, config: Dict = None) -> Tuple[Any, str]:
        """获取模型实例（支持负载均衡）"""
        if not self.running:
            return None, "服务未运行"
        
        with self.lock:
            try:
                # 确保模型池存在
                self._ensure_model_pool(algorithm_id)
                
                # 查找可用实例
                available_instances = []
                for model_id, usage_count in self.model_usage.get(algorithm_id, {}).items():
                    if usage_count < 5:  # 最大使用次数限制
                        available_instances.append((model_id, usage_count))
                
                if not available_instances:
                    # 创建新实例
                    if len(self.model_pools.get(algorithm_id, [])) < self.max_instances_per_algo:
                        model_instance, error = self.algorithm_module.get_model_instance(
                            algorithm_id, config=config
                        )
                        if model_instance:
                            model_id = f"{algorithm_id}_instance_{len(self.model_pools[algorithm_id])}"
                            self.model_pools[algorithm_id].append(model_instance)
                            self.model_usage.setdefault(algorithm_id, {})[model_id] = 1
                            logger.info(f"创建新模型实例: {model_id}")
                            return model_instance, model_id
                        else:
                            return None, f"创建模型实例失败: {error}"
                    else:
                        return None, f"算法 {algorithm_id} 已达到最大实例数限制"
                
                # 选择使用次数最少的实例
                available_instances.sort(key=lambda x: x[1])
                model_id, usage_count = available_instances[0]
                
                # 增加使用计数
                self.model_usage[algorithm_id][model_id] = usage_count + 1
                
                # 获取实例
                model_instance = self.model_pools[algorithm_id][int(model_id.split('_')[-1])]
                
                logger.debug(f"获取模型实例: {model_id}, 使用次数: {usage_count + 1}")
                return model_instance, model_id
                
            except Exception as e:
                logger.error(f"获取模型实例异常: {e}")
                return None, str(e)
    
    def release_model_instance(self, algorithm_id: str, model_id: str):
        """释放模型实例"""
        if not self.running:
            return
        
        with self.lock:
            try:
                if algorithm_id in self.model_usage and model_id in self.model_usage[algorithm_id]:
                    # 减少使用计数
                    current_usage = self.model_usage[algorithm_id][model_id]
                    if current_usage > 0:
                        self.model_usage[algorithm_id][model_id] = current_usage - 1
                        logger.debug(f"释放模型实例: {model_id}, 剩余使用次数: {current_usage - 1}")
                
            except Exception as e:
                logger.error(f"释放模型实例异常: {e}")
    
    def _ensure_model_pool(self, algorithm_id: str):
        """确保模型池存在"""
        if algorithm_id not in self.model_pools:
            self.model_pools[algorithm_id] = []
            self.model_usage[algorithm_id] = {}
    
    def _stop_all_tasks(self):
        """停止所有任务"""
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            try:
                self.stop_task(task_id)
            except Exception as e:
                logger.error(f"停止任务异常: {task_id}, {e}")
    
    def _monitor_worker(self):
        """监控线程"""
        logger.info("分析器服务监控线程启动")
        
        while self.running:
            try:
                # 监控任务状态
                for task_id, task_info in list(self.active_tasks.items()):
                    if task_info["status"] == "running":
                        # 检查任务是否仍然有效
                        current_task_info = self.task_module.get_task_info(task_id)
                        if not current_task_info:
                            logger.warning(f"任务已失效，移除: {task_id}")
                            del self.active_tasks[task_id]
                
                # 清理空闲的模型实例
                self._cleanup_idle_models()
                
            except Exception as e:
                logger.error(f"监控线程异常: {e}")
            
            time.sleep(self.monitor_interval)
        
        logger.info("分析器服务监控线程退出")
    
    def _cleanup_idle_models(self):
        """清理空闲的模型实例"""
        try:
            for algorithm_id, usage_info in self.model_usage.items():
                idle_instances = []
                for model_id, usage_count in usage_info.items():
                    if usage_count == 0:
                        idle_instances.append(model_id)
                
                # 保留至少一个实例，清理多余的
                if len(idle_instances) > 1:
                    for model_id in idle_instances[1:]:
                        try:
                            # 从池中移除
                            instance_index = int(model_id.split('_')[-1])
                            if algorithm_id in self.model_pools and len(self.model_pools[algorithm_id]) > instance_index:
                                del self.model_pools[algorithm_id][instance_index]
                            
                            # 清理使用记录
                            del usage_info[model_id]
                            
                            logger.info(f"清理空闲模型实例: {model_id}")
                        except Exception as e:
                            logger.error(f"清理模型实例异常: {model_id}, {e}")
                            
        except Exception as e:
            logger.error(f"清理空闲模型异常: {e}")
    
    def _register_event_handlers(self):
        """注册事件处理器"""
        # 监听流事件
        self.event_bus.subscribe("stream.*", self._handle_stream_event)
        
        # 监听任务事件
        self.event_bus.subscribe("task.*", self._handle_task_event)
        
        # 监听算法事件
        self.event_bus.subscribe("algorithm.*", self._handle_algorithm_event)
        
        # 监听模块状态变化事件（从service.py合并）
        self.event_bus.subscribe("module.status_changed", self._handle_module_status)
        
        # 监听告警事件（从service.py合并）
        self.event_bus.subscribe("alarm.triggered", self._handle_alarm)
    
    def _handle_stream_event(self, event: Event):
        """处理流事件"""
        try:
            event_type = event.event_type
            if event_type == "stream.added":
                logger.info(f"流添加事件: {event.data}")
            elif event_type == "stream.removed":
                logger.info(f"流移除事件: {event.data}")
            elif event_type == "stream.error":
                logger.error(f"流错误事件: {event.data}")
        except Exception as e:
            logger.error(f"处理流事件异常: {e}")
    
    def _handle_task_event(self, event: Event):
        """处理任务事件"""
        try:
            event_type = event.event_type
            if event_type == "task.created":
                logger.info(f"任务创建事件: {event.data}")
            elif event_type == "task.started":
                logger.info(f"任务启动事件: {event.data}")
            elif event_type == "task.stopped":
                logger.info(f"任务停止事件: {event.data}")
            elif event_type == "task.deleted":
                logger.info(f"任务删除事件: {event.data}")
        except Exception as e:
            logger.error(f"处理任务事件异常: {e}")
    
    def _handle_algorithm_event(self, event: Event):
        """处理算法事件"""
        try:
            event_type = event.event_type
            if event_type == "algorithm.model_module_loaded":
                logger.info(f"算法模型加载事件: {event.data}")
            elif event_type == "algorithm.postprocessor_module_loaded":
                logger.info(f"算法后处理加载事件: {event.data}")
        except Exception as e:
            logger.error(f"处理算法事件异常: {e}")
    
    def _handle_module_status(self, event: Event):
        """处理模块状态变化事件（从service.py合并）"""
        if not event.data or "module" not in event.data:
            return
            
        module_name = event.data.get("module")
        status = event.data.get("status", False)
        
        if module_name in self.modules_status:
            self.modules_status[module_name] = status
            logger.info(f"模块状态更新: {module_name} = {status}")
    
    def _handle_alarm(self, event: Event):
        """处理告警事件（从service.py合并）"""
        alarm_data = event.data
        logger.info(f"收到告警事件: {alarm_data}")
        
        # 告警处理逻辑 - 集成alarm_processor
        try:
            # 导入alarm_processor
            from ..alarm_processor import alarm_processor
            
            # 构造检测结果数据
            detection_result = {
                "task_id": alarm_data.get("task_id", ""),
                "stream_id": alarm_data.get("stream_id", ""),
                "timestamp": alarm_data.get("timestamp", datetime.now()),
                "detections": alarm_data.get("detection_result", {}).get("detections", []),
                "original_image": alarm_data.get("original_image"),
                "annotated_image": alarm_data.get("processed_image")
            }
            
            # 异步处理检测结果
            import asyncio
            if detection_result["task_id"]:
                # 创建异步任务处理告警
                task = asyncio.create_task(
                    alarm_processor.process_detection_result(
                        detection_result["task_id"], 
                        detection_result
                    )
                )
                logger.info(f"已提交告警处理任务: {alarm_data.get('alarm_id')}")
            else:
                logger.warning("告警数据缺少task_id，跳过自动处理")
                
        except Exception as e:
            logger.error(f"处理告警事件异常: {e}")
            # 确保不影响原有流程
            pass

def get_analyzer_service():
    """获取分析器服务实例"""
    return AnalyzerService.get_instance() 