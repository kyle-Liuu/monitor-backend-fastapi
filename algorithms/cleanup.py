"""
算法包目录清理脚本
- 清理缓存文件
- 删除临时文件
- 整理目录结构
"""

import os
import shutil
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_cache_files():
    """清理缓存文件"""
    try:
        # 清理 __pycache__ 目录
        cache_dirs = []
        for root, dirs, files in os.walk("."):
            for dir_name in dirs:
                if dir_name == "__pycache__":
                    cache_dirs.append(os.path.join(root, dir_name))
        
        for cache_dir in cache_dirs:
            shutil.rmtree(cache_dir)
            logger.info(f"已删除缓存目录: {cache_dir}")
        
        # 清理 .pyc 文件
        pyc_files = []
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith(".pyc"):
                    pyc_files.append(os.path.join(root, file))
        
        for pyc_file in pyc_files:
            os.remove(pyc_file)
            logger.info(f"已删除缓存文件: {pyc_file}")
            
    except Exception as e:
        logger.error(f"清理缓存文件失败: {e}")

def cleanup_temp_files():
    """清理临时文件"""
    try:
        # 清理临时文件
        temp_extensions = [".tmp", ".temp", ".log", ".bak"]
        temp_files = []
        
        for root, dirs, files in os.walk("."):
            for file in files:
                for ext in temp_extensions:
                    if file.endswith(ext):
                        temp_files.append(os.path.join(root, file))
        
        for temp_file in temp_files:
            os.remove(temp_file)
            logger.info(f"已删除临时文件: {temp_file}")
            
    except Exception as e:
        logger.error(f"清理临时文件失败: {e}")

def cleanup_uploads():
    """清理上传目录中的旧文件"""
    try:
        uploads_dir = Path("uploads")
        if uploads_dir.exists():
            # 获取所有ZIP文件
            zip_files = list(uploads_dir.glob("*.zip"))
            
            for zip_file in zip_files:
                # 检查是否已安装
                package_name = zip_file.stem
                installed_dir = Path("installed") / package_name
                
                if installed_dir.exists():
                    # 如果已安装，删除ZIP文件
                    zip_file.unlink()
                    logger.info(f"已删除已安装的ZIP文件: {zip_file}")
                    
    except Exception as e:
        logger.error(f"清理上传目录失败: {e}")

def validate_directory_structure():
    """验证目录结构"""
    try:
        required_dirs = ["installed", "uploads", "registry"]
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"创建目录: {dir_name}")
        
        # 检查核心文件
        core_files = [
            "base_classes.py",
            "package_manager.py", 
            "package_algorithm.py",
            "usage_example.py"
        ]
        
        missing_files = []
        for file_name in core_files:
            if not Path(file_name).exists():
                missing_files.append(file_name)
        
        if missing_files:
            logger.warning(f"缺少核心文件: {missing_files}")
        else:
            logger.info("所有核心文件存在")
            
    except Exception as e:
        logger.error(f"验证目录结构失败: {e}")

def main():
    """主清理函数"""
    logger.info("开始清理算法包目录...")
    
    # 切换到算法包目录
    original_dir = os.getcwd()
    algorithms_dir = Path(__file__).parent
    
    try:
        os.chdir(algorithms_dir)
        
        # 执行清理操作
        cleanup_cache_files()
        cleanup_temp_files()
        cleanup_uploads()
        validate_directory_structure()
        
        logger.info("算法包目录清理完成")
        
    except Exception as e:
        logger.error(f"清理过程出错: {e}")
    
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    main() 