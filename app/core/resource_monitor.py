import psutil
import threading
import time
import logging
import os
from typing import Dict, Any, List, Optional
import torch

from .logger import setup_logger
from .config import (
    MAX_CPU_PERCENT, MAX_MEMORY_PERCENT, MAX_GPU_PERCENT,
    ENABLE_RESOURCE_CONTROL
)

# 创建日志器
logger = setup_logger("resource_monitor")

class ResourceMonitor:
    """资源监控器，监控和管理系统资源使用"""
    
    def __init__(self):
        self.stats: Dict[str, Any] = {
            "cpu_usage": 0,
            "memory_usage": 0,
            "gpu_usage": 0,
            "active_streams": 0,
            "processed_frames": 0,
            "dropped_frames": 0,
            "slot_usage": 0,
            "disk_usage": 0,
            "network_io": {
                "bytes_sent": 0,
                "bytes_recv": 0
            }
        }
        self.monitor_thread = None
        self.running = False
        self.lock = threading.RLock()
        self.callbacks = []
        self.last_update = 0
        self.last_net_io = None
    
    def start(self, interval: float = 5.0) -> bool:
        """启动资源监控"""
        with self.lock:
            if self.running:
                logger.warning("资源监控已在运行")
                return False
            
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(interval,),
                daemon=True,
                name="resource_monitor"
            )
            self.monitor_thread.start()
            logger.info(f"资源监控已启动，间隔: {interval}秒")
            return True
    
    def stop(self) -> bool:
        """停止资源监控"""
        with self.lock:
            if not self.running:
                logger.warning("资源监控未在运行")
                return False
            
            self.running = False
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=5.0)
            
            logger.info("资源监控已停止")
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取资源统计信息"""
        with self.lock:
            return self.stats.copy()
    
    def update_stat(self, key: str, value: Any) -> None:
        """更新特定统计信息"""
        with self.lock:
            if key in self.stats:
                self.stats[key] = value
    
    def register_callback(self, callback) -> None:
        """注册资源变化回调函数"""
        with self.lock:
            if callback not in self.callbacks:
                self.callbacks.append(callback)
    
    def unregister_callback(self, callback) -> None:
        """注销资源变化回调函数"""
        with self.lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)
    
    def check_resource_limits(self) -> Dict[str, Any]:
        """检查资源是否超过限制"""
        with self.lock:
            if not ENABLE_RESOURCE_CONTROL:
                return {"ok": True, "message": "资源控制已禁用"}
            
            result = {"ok": True, "message": "", "details": {}}
            
            # 检查CPU使用率
            if self.stats["cpu_usage"] > MAX_CPU_PERCENT:
                result["ok"] = False
                result["message"] = f"CPU使用率过高: {self.stats['cpu_usage']:.1f}% > {MAX_CPU_PERCENT}%"
                result["details"]["cpu"] = {
                    "current": self.stats["cpu_usage"],
                    "limit": MAX_CPU_PERCENT
                }
            
            # 检查内存使用率
            if self.stats["memory_usage"] > MAX_MEMORY_PERCENT:
                result["ok"] = False
                result["message"] = f"内存使用率过高: {self.stats['memory_usage']:.1f}% > {MAX_MEMORY_PERCENT}%"
                result["details"]["memory"] = {
                    "current": self.stats["memory_usage"],
                    "limit": MAX_MEMORY_PERCENT
                }
            
            # 检查GPU使用率
            if torch.cuda.is_available() and self.stats["gpu_usage"] > MAX_GPU_PERCENT:
                result["ok"] = False
                result["message"] = f"GPU使用率过高: {self.stats['gpu_usage']:.1f}% > {MAX_GPU_PERCENT}%"
                result["details"]["gpu"] = {
                    "current": self.stats["gpu_usage"],
                    "limit": MAX_GPU_PERCENT
                }
            
            return result
    
    def _monitor_loop(self, interval: float) -> None:
        """资源监控循环"""
        self.last_net_io = psutil.net_io_counters()
        
        while self.running:
            try:
                # 更新CPU使用率
                self.stats["cpu_usage"] = psutil.cpu_percent()
                
                # 更新内存使用率
                memory = psutil.virtual_memory()
                self.stats["memory_usage"] = memory.percent
                
                # 更新GPU使用率
                if torch.cuda.is_available():
                    try:
                        # 清理缓存以获取准确的使用率
                        torch.cuda.empty_cache()
                        
                        # 计算所有GPU的平均使用率
                        total_memory = 0
                        used_memory = 0
                        for i in range(torch.cuda.device_count()):
                            props = torch.cuda.get_device_properties(i)
                            total_memory += props.total_memory
                            used_memory += torch.cuda.memory_allocated(i) + torch.cuda.memory_reserved(i)
                        
                        if total_memory > 0:
                            self.stats["gpu_usage"] = (used_memory / total_memory) * 100
                        else:
                            self.stats["gpu_usage"] = 0
                    except Exception as e:
                        logger.error(f"获取GPU使用率异常: {e}")
                        self.stats["gpu_usage"] = 0
                
                # 更新磁盘使用率
                disk = psutil.disk_usage(os.path.abspath('.'))
                self.stats["disk_usage"] = disk.percent
                
                # 更新网络IO
                net_io = psutil.net_io_counters()
                if self.last_net_io:
                    self.stats["network_io"] = {
                        "bytes_sent": net_io.bytes_sent - self.last_net_io.bytes_sent,
                        "bytes_recv": net_io.bytes_recv - self.last_net_io.bytes_recv
                    }
                self.last_net_io = net_io
                
                # 更新时间戳
                self.last_update = time.time()
                
                # 调用回调函数
                for callback in self.callbacks:
                    try:
                        callback(self.stats)
                    except Exception as e:
                        logger.error(f"资源监控回调异常: {e}")
                
                # 定期记录资源使用情况
                if int(time.time()) % 60 < interval:  # 每分钟记录一次
                    logger.info(
                        f"系统资源: CPU={self.stats['cpu_usage']:.1f}%, "
                        f"内存={self.stats['memory_usage']:.1f}%, "
                        f"GPU={self.stats['gpu_usage']:.1f}%, "
                        f"磁盘={self.stats['disk_usage']:.1f}%"
                    )
                
                # 等待下一次更新
                time.sleep(interval)
            
            except Exception as e:
                logger.error(f"资源监控异常: {e}")
                time.sleep(interval * 2)  # 出错后等待更长时间

# 全局资源监控器实例
resource_monitor = ResourceMonitor()

def get_resource_monitor():
    """获取全局资源监控器实例"""
    return resource_monitor

# 启动资源监控
def start_resource_monitor():
    """启动资源监控"""
    return resource_monitor.start()

# 在应用启动时调用
def init_resource_monitor():
    """初始化资源监控"""
    start_resource_monitor()

# 导出
__all__ = [
    "ResourceMonitor", "resource_monitor", "get_resource_monitor",
    "start_resource_monitor", "init_resource_monitor"
] 