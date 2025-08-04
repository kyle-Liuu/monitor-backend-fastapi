"""
进程管理器模块
- 统一进程调度/生命周期/任务管理/流复用/健康监控
- create_task: 一条流多算法多推流，自动流复用、模型池分配、推流开关
- stop_process/stop_all: 优雅退出，进程健康监控，异常自动重启
- 状态监控：定期检查所有进程健康，自动重启异常进程
- 进程命名、日志、异常风格统一
- 只保留分析器主线相关内容
"""

import multiprocessing as mp
import logging
import time
import signal
import os
import sys
import psutil
import json
import threading
import atexit
import copy
import uuid
from multiprocessing import context, Manager
from .ipc_manager import IPCManager
from .model_manager import ModelRegistry
from .worker_processes import stream_process, algorithm_process, streaming_process, alarm_process

logger = logging.getLogger(__name__)

# 进程管理器实例ID，用于创建共享资源名称
MANAGER_ID = str(uuid.uuid4())[:8]

class ProcessManager:
    """进程管理器，负责创建和管理各种工作进程"""
    
    def __init__(self):
        """初始化进程管理器"""
        # 进程容器
        self.processes = {}
        
        # 管理器ID
        self.manager_id = MANAGER_ID
        
        # 停止事件
        self.stop_event = mp.Event()
        
        # 进程间通信管理器
        self.ipc_manager = IPCManager(max_queue_size=100)
        
        # 模型管理器
        self.model_registry = ModelRegistry()
        
        # WebSocket配置
        self.websocket_url = "ws://localhost:8001/api/ws/alarms"
        
        # 监控线程（改用线程而不是进程来避免序列化问题）
        self.monitor_thread = None
        self.monitor_interval = 10  # 秒
        
        # 初始化标志
        self.initialized = False
        
        # 优雅退出标志
        self.is_shutting_down = False
        
        # 新增：流复用相关
        self.stream_queues = {}      # stream_id: 帧队列
        self.stream_ref_count = {}   # stream_id: 使用计数
        
        # 注册退出处理函数
        atexit.register(self._cleanup_on_exit)
    
    def initialize(self):
        """初始化管理器"""
        if self.initialized:
            return True
        
        logger.info("正在初始化进程管理器...")
        
        # 设置信号处理
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except Exception as e:
            logger.warning(f"无法设置信号处理器: {e}")
        
        # 启动监控线程
        self.start_monitor()
        
        self.initialized = True
        logger.info("进程管理器初始化完成")
        
        return True
    
    def _signal_handler(self, sig, frame):
        """信号处理器 - 确保进程能正确退出"""
        if self.is_shutting_down:
            logger.warning("检测到重复关闭信号，将立即强制退出...")
            os._exit(0)  # 直接强制退出
            
        logger.info(f"接收到信号: {sig}, 准备关闭...")
        self.is_shutting_down = True
        
        # 设置一个非常短的超时时间（1秒）
        def force_exit():
            logger.warning("关闭超时，强制终止进程...")
            try:
                # 尝试进行最小化清理
                self.stop_event.set()
            except:
                pass
            finally:
                # 强制退出不再等待
                os._exit(0)
        
        # 创建并立即启动定时器
        timer = threading.Timer(5.0, force_exit)
        timer.daemon = True
        timer.start()
        
        try:
            # 标记停止事件
            self.stop_event.set()
            # 执行快速关闭
            self.quick_shutdown()
        except Exception as e:
            logger.error(f"关闭过程中发生异常: {e}")
            # 发生异常时直接退出
            os._exit(0)
    
    def quick_shutdown(self):
        """快速关闭所有进程，不等待"""
        logger.info("正在快速关闭进程管理器...")
        
        # 设置停止事件
        self.stop_event.set()
        
        # 立即终止所有进程
        for process_id, process_info in list(self.processes.items()):
            process = process_info['process']
            if process and process.is_alive():
                try:
                    # 直接使用kill而不是terminate
                    process.kill()
                except:
                    pass
        
        # 清空进程列表
        self.processes.clear()
        
        # 尝试清理共享资源
        try:
            self.ipc_manager.cleanup()
        except:
            pass
        
        logger.info("进程管理器已关闭")
    
    def _forced_cleanup(self):
        """强制清理资源，用于关闭超时情况"""
        logger.warning("执行强制资源清理...")
        try:
            # 立即终止所有子进程
            for process_id, process_info in list(self.processes.items()):
                process = process_info['process']
                if process.is_alive():
                    logger.warning(f"强制终止进程: {process_id}")
                    process.kill()
                    
            # 清理共享资源
            self.ipc_manager.cleanup()
        except Exception as e:
            logger.error(f"强制清理过程中发生异常: {e}")
            
    def _cleanup_on_exit(self):
        """确保在Python解释器退出时清理资源"""
        if not self.is_shutting_down:
            logger.info("程序退出，执行最终清理...")
            try:
                # 设置停止事件
                self.stop_event.set()
                # 关闭所有进程
                for process_id, process_info in list(self.processes.items()):
                    process = process_info['process']
                    if process.is_alive():
                        process.terminate()
                # 清理IPC资源
                self.ipc_manager.cleanup()
            except Exception as e:
                logger.error(f"退出清理过程中发生异常: {e}")
    
    def start_monitor(self):
        """启动监控线程"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        # 使用线程而不是进程，避免序列化问题
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker,
            args=()  # 不传递self，避免序列化问题
        )
        self.monitor_thread.daemon = True
        
        try:
            self.monitor_thread.start()
            logger.info("监控线程已启动")
        except Exception as e:
            logger.error(f"启动监控线程失败: {e}", exc_info=True)
    
    def _monitor_worker(self):
        """监控工作进程，收集状态信息"""
        threading.current_thread().name = "Thread-Monitor"
        
        while not self.stop_event.is_set():
            try:
                # 收集所有进程状态
                for process_id, process_info in list(self.processes.items()):
                    process = process_info['process']
                    
                    if not process.is_alive():
                        # 进程已死亡
                        logger.warning(f"进程已死亡: {process_id}, 类型: {process_info['type']}")
                        
                        # 如果配置了自动重启，则重启进程
                        if process_info.get('auto_restart', False):
                            logger.info(f"正在重启进程: {process_id}")
                            self._restart_process(process_id)
                
                # 检查内存使用情况
                try:
                    process = psutil.Process(os.getpid())
                    memory_info = process.memory_info()
                    memory_usage_mb = memory_info.rss / (1024 * 1024)
                    
                    logger.info(f"当前内存使用: {memory_usage_mb:.2f}MB")
                except Exception as e:
                    logger.warning(f"无法获取内存使用信息: {e}")
                
                # 更多监控逻辑...
                
                # 休眠
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"监控线程异常: {e}", exc_info=True)
                time.sleep(5)
    
    def _restart_process(self, process_id):
        """重启指定进程"""
        if process_id not in self.processes:
            logger.warning(f"找不到进程 {process_id}，无法重启")
            return False
        
        process_info = self.processes[process_id]
        
        try:
            # 关闭现有进程
            if process_info['process'].is_alive():
                process_info['process'].terminate()
                process_info['process'].join(timeout=5)
                
                if process_info['process'].is_alive():
                    process_info['process'].kill()
            
            # 创建新进程
            process_type = process_info['type']
            
            if process_type == 'stream':
                stream_id = process_info['stream_id']
                stream_url = process_info['stream_url']
                
                new_process = mp.Process(
                    target=stream_process_worker,
                    args=(self.manager_id, stream_id, stream_url)
                )
                
            elif process_type == 'algorithm':
                stream_id = process_info['stream_id']
                algo_id = process_info['algo_id']
                model_id = process_info['model_id']
                
                new_process = mp.Process(
                    target=algorithm_process_worker,
                    args=(self.manager_id, stream_id, algo_id, model_id)
                )
                
            elif process_type == 'streaming':
                stream_id = process_info['stream_id']
                algo_id = process_info['algo_id']
                output_url = process_info['output_url']
                
                new_process = mp.Process(
                    target=streaming_process_worker,
                    args=(self.manager_id, stream_id, algo_id, output_url)
                )
                
            elif process_type == 'alarm':
                new_process = mp.Process(
                    target=alarm_process_worker,
                    args=(self.manager_id, self.websocket_url)
                )
                
            else:
                logger.error(f"未知进程类型: {process_type}")
                return False
            
            # 启动新进程
            new_process.daemon = False  # 不设置为守护进程，避免子进程创建限制
            new_process.start()
            
            # 更新进程引用
            self.processes[process_id]['process'] = new_process
            
            logger.info(f"进程已重启: {process_id}, 新PID: {new_process.pid}")
            return True
        except Exception as e:
            logger.error(f"重启进程 {process_id} 失败: {e}", exc_info=True)
            return False
    
    def start_stream_process(self, stream_id, stream_url, auto_restart=True):
        """启动拉流进程"""
        process_id = f"stream_{stream_id}"
        
        # 检查是否已存在
        if process_id in self.processes:
            logger.warning(f"拉流进程已存在: {stream_id}")
            return False
        
        try:
            # 创建进程
            process = mp.Process(
                target=stream_process_worker,
                args=(self.manager_id, stream_id, stream_url)
            )
            
            # 保存进程信息
            self.processes[process_id] = {
                'process': process,
                'type': 'stream',
                'stream_id': stream_id,
                'stream_url': stream_url,
                'auto_restart': auto_restart
            }
            
            # 启动进程
            process.daemon = False  # 不设置为守护进程，避免子进程创建限制
            process.start()
            
            logger.info(f"拉流进程已启动: {stream_id}, PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"启动拉流进程失败: {e}", exc_info=True)
            return False
    
    def start_algorithm_process(self, stream_id, algo_id, algo_package, model_name, model_config, auto_restart=True):
        """启动算法处理进程"""
        process_id = f"algo_{stream_id}_{algo_id}"
        
        # 检查是否已存在
        if process_id in self.processes:
            logger.warning(f"算法进程已存在: {stream_id}_{algo_id}")
            return False
        
        try:
            # 注册模型
            model_id = self.model_registry.register_model(algo_package, model_name, model_config)
            
            # 获取模型实例数配置，默认为1
            num_instances = model_config.get('model_pool_size', 1)
            
            # 加载模型
            if not self.model_registry.load_model(model_id, num_instances=num_instances):
                logger.error(f"无法加载模型: {model_id}")
                return False
            
            # 创建进程
            process = mp.Process(
                target=algorithm_process_worker,
                args=(self.manager_id, stream_id, algo_id, model_id, algo_package, model_name)
            )
            
            # 保存进程信息
            self.processes[process_id] = {
                'process': process,
                'type': 'algorithm',
                'stream_id': stream_id,
                'algo_id': algo_id,
                'model_id': model_id,
                'auto_restart': auto_restart
            }
            
            # 启动进程
            process.daemon = False
            process.start()
            
            logger.info(f"算法进程已启动: {stream_id}_{algo_id}, PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"启动算法进程失败: {e}", exc_info=True)
            return False
    
    def start_streaming_process(self, stream_id, algo_id, output_url, auto_restart=True):
        """启动推流进程"""
        process_id = f"stream_out_{stream_id}_{algo_id}"
        
        # 检查是否已存在
        if process_id in self.processes:
            logger.warning(f"推流进程已存在: {stream_id}_{algo_id}")
            return False
        
        try:
            # 创建进程
            process = mp.Process(
                target=streaming_process_worker,
                args=(self.manager_id, stream_id, algo_id, output_url)
            )
            
            # 保存进程信息
            self.processes[process_id] = {
                'process': process,
                'type': 'streaming',
                'stream_id': stream_id,
                'algo_id': algo_id,
                'output_url': output_url,
                'auto_restart': auto_restart
            }
            
            # 启动进程
            process.daemon = False
            process.start()
            
            logger.info(f"推流进程已启动: {stream_id}_{algo_id}, PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"启动推流进程失败: {e}", exc_info=True)
            return False
    
    def start_alarm_process(self, websocket_url=None, auto_restart=True):
        """启动告警处理进程"""
        process_id = "alarm_handler"
        
        # 检查是否已存在
        if process_id in self.processes:
            logger.warning("告警处理进程已存在")
            return False
        
        try:
            # 使用指定的websocket_url或默认值
            if websocket_url:
                self.websocket_url = websocket_url
            
            # 创建进程
            process = mp.Process(
                target=alarm_process_worker,
                args=(self.manager_id, self.websocket_url)
            )
            
            # 保存进程信息
            self.processes[process_id] = {
                'process': process,
                'type': 'alarm',
                'auto_restart': auto_restart
            }
            
            # 启动进程
            process.daemon = False
            process.start()
            
            logger.info(f"告警处理进程已启动, PID: {process.pid}")
            return True
        except Exception as e:
            logger.error(f"启动告警处理进程失败: {e}", exc_info=True)
            return False
    
    def stop_process(self, process_id):
        """停止指定进程"""
        if process_id not in self.processes:
            logger.warning(f"进程不存在: {process_id}")
            return False
        
        try:
            process_info = self.processes[process_id]
            process = process_info['process']
            
            # 终止进程
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                
                if process.is_alive():
                    logger.warning(f"进程未能正常终止，强制结束: {process_id}")
                    process.kill()
                    process.join()
            
            # 移除进程记录
            del self.processes[process_id]
            
            logger.info(f"进程已停止: {process_id}")
            return True
        except Exception as e:
            logger.error(f"停止进程 {process_id} 失败: {e}", exc_info=True)
            return False
    
    def create_task(self, task_id, stream_id, stream_url, algo_id, algo_package, model_name, model_config, output_url=None, enable_output=True):
        """创建完整的处理任务（拉流+算法+推流）"""
        try:
            # 1. 流复用：同一路流只拉一次
            if stream_id not in self.stream_queues:
                frame_queue = self.ipc_manager.create_stream_queue(stream_id)
                self.stream_queues[stream_id] = frame_queue
                self.stream_ref_count[stream_id] = 1
                self.start_stream_process(stream_id, stream_url)
            else:
                self.stream_ref_count[stream_id] += 1
                frame_queue = self.stream_queues[stream_id]
            # 2. 启动算法进程（支持模型池）
            model_id = self.model_registry.register_model(algo_package, model_name, model_config)
            # 获取模型实例数配置，默认为1
            num_instances = model_config.get('model_pool_size', 1)
            self.model_registry.load_model(model_id, num_instances=num_instances)
            result_queue = self.ipc_manager.create_result_queue(stream_id, algo_id)
            self.start_algorithm_process(stream_id, algo_id, algo_package, model_name, model_config)
            # 3. 推流进程（可配置开关，支持动态增删）
            stream_out_id = f"stream_out_{stream_id}_{algo_id}"
            if enable_output and output_url:
                if stream_out_id not in self.processes:
                    self.start_streaming_process(stream_id, algo_id, output_url)
                else:
                    logger.info(f"推流进程已存在: {stream_out_id}")
            elif not enable_output:
                # 如果已存在推流进程但现在不需要，关闭它
                if stream_out_id in self.processes:
                    self.stop_process(stream_out_id)
            # 4. 告警进程（如未启动）
            if "alarm_handler" not in self.processes:
                self.start_alarm_process()
            # 5. 记录任务与进程映射关系（可扩展）
            return True, f"任务创建成功: {task_id}"
        except Exception as e:
            logger.error(f"创建任务异常: {e}", exc_info=True)
            return False, f"创建任务失败: {str(e)}"
    
    def stop_task(self, stream_id, algo_id, stop_output=True, stop_algo=True):
        """停止完整的处理任务"""
        try:
            # 支持单独关闭推流进程
            stream_out_id = f"stream_out_{stream_id}_{algo_id}"
            if stop_output and stream_out_id in self.processes:
                self.stop_process(stream_out_id)
            # 支持单独关闭算法进程
            algo_process_id = f"algo_{stream_id}_{algo_id}"
            if stop_algo and algo_process_id in self.processes:
                self.stop_process(algo_process_id)
            # 新增：流复用引用计数
            if stop_algo and stream_id in self.stream_ref_count:
                self.stream_ref_count[stream_id] -= 1
                if self.stream_ref_count[stream_id] <= 0:
                    # 没有其他算法/推流在用，停止拉流进程
                    stream_process_id = f"stream_{stream_id}"
                    if stream_process_id in self.processes:
                        self.stop_process(stream_process_id)
                    self.stream_ref_count.pop(stream_id)
                    self.stream_queues.pop(stream_id)
            return True, "任务停止成功"
        except Exception as e:
            logger.error(f"停止任务异常: {e}", exc_info=True)
            return False, f"停止任务失败: {str(e)}"
    
    def get_status(self):
        """获取当前状态"""
        # 获取进程状态
        processes = {}
        for process_id, info in self.processes.items():
            if info['process'].is_alive():
                processes[process_id] = {
                    'pid': info['process'].pid,
                    'type': info['type'],
                    'alive': True
                }
            else:
                processes[process_id] = {
                    'pid': None,
                    'type': info['type'],
                    'alive': False
                }
        
        # 获取共享状态
        streams = self.ipc_manager.get_stream_status()
        algorithms = self.ipc_manager.get_algo_status()
        outputs = self.ipc_manager.get_output_status()
        
        return {
            'processes': processes,
            'streams': streams,
            'algorithms': algorithms,
            'outputs': outputs,
            'memory_usage': self._get_memory_usage()
        }
    
    def shutdown(self):
        """关闭所有进程并清理资源"""
        logger.info("正在关闭进程管理器...")
        
        # 设置停止事件
        self.stop_event.set()
        self.is_shutting_down = True
        
        try:
            # 停止所有进程
            for process_id, process_info in list(self.processes.items()):
                process = process_info['process']
                
                logger.info(f"正在停止进程: {process_id}, PID: {process.pid if process.is_alive() else 'N/A'}")
                
                if process.is_alive():
                    process.terminate()
                    # 设置较短的等待时间，避免卡住
                    process.join(timeout=2)
                    
                    if process.is_alive():
                        logger.warning(f"进程未响应终止信号，强制结束: {process_id}")
                        process.kill()
                        process.join(timeout=1)
            
            # 清空进程列表
            self.processes.clear()
            
            # 清理共享资源
            self.ipc_manager.cleanup()
            
            logger.info("进程管理器已关闭")
            
            # 取消注册退出处理函数，避免重复调用
            atexit.unregister(self._cleanup_on_exit)
            
        except Exception as e:
            logger.error(f"关闭进程管理器时发生错误: {e}", exc_info=True)

    def _get_memory_usage(self):
        """获取当前进程的内存使用情况（MB）"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)  # 转换为MB
        except ImportError:
            return 0  # 如果psutil不可用，返回0
        except Exception as e:
            logger.error(f"获取内存使用情况失败: {e}")
            return 0


# ============= 进程包装函数 =============
def create_stop_event():
    """创建停止事件"""
    return mp.Event()

def stream_process_worker(manager_id, stream_id, stream_url):
    """拉流进程工作函数"""
    try:
        # 创建本地对象
        stop_event = create_stop_event()
        ipc_manager = IPCManager(max_queue_size=100, manager_id=manager_id)
        
        # 设置进程名称
        mp.current_process().name = f"Stream-{stream_id}"
        
        logger.info(f"拉流进程初始化: manager_id={manager_id}, stream_id={stream_id}, url={stream_url}")
        
        # 执行实际工作
        stream_process(stream_id, stream_url, ipc_manager, stop_event)
    except Exception as e:
        logger.error(f"拉流进程异常: {e}", exc_info=True)

def algorithm_process_worker(manager_id, stream_id, algo_id, model_id, algo_package, model_name):
    """算法处理进程工作函数"""
    try:
        # 创建本地对象
        stop_event = create_stop_event()
        ipc_manager = IPCManager(max_queue_size=100, manager_id=manager_id)
        model_registry = ModelRegistry()
        
        # 设置进程名称
        mp.current_process().name = f"Algo-{stream_id}-{algo_id}"
        
        logger.info(f"算法进程初始化: manager_id={manager_id}, stream_id={stream_id}, algo_id={algo_id}, model_id={model_id}")
        
        # 在algorithm_process_worker内部，直接用传入的algo_package和model_name参数。
        # 删除所有对model_id的split、algo_package的默认赋值、model_name的推断等逻辑。
        # 例如：
        # model_registry.register_model(algo_package, model_name, ...)
        # model_registry.load_model(model_id, ...)
        # 其余逻辑保持不变。
        try:        
            # 自动注册和加载模型
            logger.info(f"正在自动注册模型: {model_id} (包:{algo_package}, 模型:{model_name})")
            
            # 注册模型
            model_registry.register_model(algo_package, model_name, {})
            
            # 加载模型
            success = model_registry.load_model(model_id, num_instances=1)
            if not success:
                logger.error(f"自动加载模型失败: {model_id}")
        except Exception as e:
            logger.error(f"自动注册模型异常: {e}", exc_info=True)
        
        # 执行实际工作
        algorithm_process(stream_id, algo_id, model_id, ipc_manager, model_registry, stop_event)
    except Exception as e:
        logger.error(f"算法进程异常: {e}", exc_info=True)

def streaming_process_worker(manager_id, stream_id, algo_id, output_url):
    """推流进程工作函数"""
    try:
        # 创建本地对象
        stop_event = create_stop_event()
        ipc_manager = IPCManager(max_queue_size=100, manager_id=manager_id)
        
        # 设置进程名称
        mp.current_process().name = f"Stream-Out-{stream_id}-{algo_id}"
        
        logger.info(f"推流进程初始化: manager_id={manager_id}, stream_id={stream_id}, algo_id={algo_id}, output_url={output_url}")
        
        # 执行实际工作
        streaming_process(stream_id, algo_id, output_url, ipc_manager, stop_event)
    except Exception as e:
        logger.error(f"推流进程异常: {e}", exc_info=True)

def alarm_process_worker(manager_id, websocket_url):
    """告警处理进程工作函数"""
    try:
        # 创建本地对象
        stop_event = create_stop_event()
        ipc_manager = IPCManager(max_queue_size=100, manager_id=manager_id)
        
        # 设置进程名称
        mp.current_process().name = f"Alarm-Handler"
        
        logger.info(f"告警处理进程初始化: manager_id={manager_id}, websocket_url={websocket_url}")
        
        # 执行实际工作
        alarm_process(ipc_manager, websocket_url, stop_event)
    except Exception as e:
        logger.error(f"告警处理进程异常: {e}", exc_info=True) 

# 全局进程管理器实例
_process_manager = None

def get_process_manager():
    """获取全局进程管理器实例"""
    global _process_manager
    if _process_manager is None:
        _process_manager = ProcessManager()
        _process_manager.initialize()
    return _process_manager 