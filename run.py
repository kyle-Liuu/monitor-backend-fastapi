"""
FastAPI应用启动脚本
"""
import argparse
import uvicorn
import logging
import sys
import os
import signal
import multiprocessing
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("logs", "app.log"), mode="a")
    ]
)
logger = logging.getLogger(__name__)

# 确保logs目录存在
os.makedirs("logs", exist_ok=True)

# 记录进程ID，用于管理进程
def write_pid_file():
    """写入进程ID到文件"""
    pid = os.getpid()
    try:
        with open("video_detection.pid", "w") as f:
            f.write(str(pid))
        logger.info(f"进程ID {pid} 已写入 video_detection.pid")
    except Exception as e:
        logger.error(f"写入进程ID文件失败: {e}")

# 清理进程ID文件
def cleanup_pid_file():
    """清理进程ID文件"""
    try:
        if os.path.exists("video_detection.pid"):
            os.remove("video_detection.pid")
            logger.info("已清理进程ID文件")
    except Exception as e:
        logger.error(f"清理进程ID文件失败: {e}")

# 信号处理函数
def handle_signal(signum, frame):
    """处理终止信号"""
    # 如果已经在关闭中，直接强制退出
    if hasattr(handle_signal, "is_shutting_down") and handle_signal.is_shutting_down:
        logger.warning("检测到重复终止信号，强制退出...")
        os._exit(0)  # 直接强制退出
        
    handle_signal.is_shutting_down = True
    
    signals = {
        signal.SIGINT: "SIGINT",
        signal.SIGTERM: "SIGTERM"
    }
    signal_name = signals.get(signum, f"信号 {signum}")
    
    logger.info(f"接收到 {signal_name}，正在清理并退出...")
    
    # 清理资源
    try:
        cleanup_pid_file()
    except:
        pass
    
    # 非常短的超时，1秒后强制退出
    def force_exit():
        logger.warning("执行强制退出...")
        os._exit(0)
    
    # 创建并立即启动定时器
    timer = threading.Timer(1.0, force_exit)
    timer.daemon = True
    timer.start()
    
    # 不再调用sys.exit，让定时器自然触发

def main():
    """主函数"""
    try:
        # Windows平台多进程支持
        if sys.platform == 'win32':
            multiprocessing.freeze_support()
        
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='AI视频监控系统API服务')
        parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址')
        parser.add_argument('--port', type=int, default=8001, help='监听端口')
        parser.add_argument('--reload', action='store_true', help='启用热重载（开发模式）')
        parser.add_argument('--workers', type=int, default=1, help='工作进程数')
        parser.add_argument('--log-level', type=str, default='info', 
                           choices=['debug', 'info', 'warning', 'error', 'critical'], 
                           help='日志级别')
        
        args = parser.parse_args()
        
        # 写入进程ID
        write_pid_file()
        
        # 设置信号处理
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        # 启动服务
        logger.info(f"启动 API 服务，监听地址: {args.host}:{args.port}")
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers,
            log_level=args.log_level
        )
    except KeyboardInterrupt:
        logger.info("收到键盘中断，正在退出...")
        cleanup_pid_file()
    except Exception as e:
        logger.error(f"启动API服务时发生错误: {e}", exc_info=True)
        cleanup_pid_file()
        sys.exit(1)
    finally:
        cleanup_pid_file()
        logger.info("服务已关闭")

if __name__ == "__main__":
    main() 