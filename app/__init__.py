# 导入核心模块
from .core.logger import logger
from .core.config import CONFIG
# 共享内存功能已移至 analyzer/memory/shared_memory.py
# from .core.shared_memory import init_shared_memory, cleanup_shared_memory
from .core.resource_monitor import init_resource_monitor

# 延迟导入 process_manager，避免循环导入问题
def get_process_manager():
    """获取进程管理器实例"""
    from ..core.process_manager import get_process_manager as _get_process_manager
    return _get_process_manager()

# 初始化函数
def init_app():
    """初始化应用"""
    logger.info("初始化应用...")
    
    # 共享内存功能已移至 analyzer/memory/shared_memory.py
    # 初始化共享内存
    # if init_shared_memory():
    #     logger.info("共享内存初始化成功")
    # else:
    #     logger.error("共享内存初始化失败")
    
    # 初始化资源监控
    init_resource_monitor()
    logger.info("资源监控初始化成功")
    
    # 注册清理函数
    import atexit
    atexit.register(cleanup_app)
    
    logger.info("应用初始化完成")

def cleanup_app():
    """清理应用资源"""
    logger.info("清理应用资源...")
    
    # 停止所有进程
    process_manager = get_process_manager()
    process_manager.cleanup_all()
    
    # 共享内存功能已移至 analyzer/memory/shared_memory.py
    # 清理共享内存
    # cleanup_shared_memory()
    
    logger.info("应用资源清理完成") 