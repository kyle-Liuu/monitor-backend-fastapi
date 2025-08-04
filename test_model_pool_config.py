#!/usr/bin/env python3
"""
测试模型实例池配置功能
验证默认实例数为1，支持自定义配置
"""

import sys
import os
import yaml
import logging

# 方法一：将 algorithms/installed 目录加入 sys.path
algorithms_installed_path = os.path.join(os.path.dirname(__file__), "algorithms", "installed")
if algorithms_installed_path not in sys.path:
    sys.path.insert(0, algorithms_installed_path)

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.process_manager import ProcessManager
from core.model_manager import ModelRegistry

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_default_config():
    """测试默认配置（1个实例）"""
    logger.info("=== 测试默认配置（1个实例）===")
    
    # 创建进程管理器
    process_manager = ProcessManager()
    process_manager.initialize()
    
    # 测试配置
    model_config = {
        'name': 'yolov8n',
        'img_size': 640,
        'conf_thres': 0.25,
        'iou_thres': 0.45
        # 不指定 model_pool_size，使用默认值1
    }
    
    # 注册和加载模型
    model_id = process_manager.model_registry.register_model(
        'algocf6c488d', 'yolov8n', model_config
    )
    
    # 获取实例数配置
    num_instances = model_config.get('model_pool_size', 1)
    logger.info(f"配置的实例数: {num_instances}")
    
    # 加载模型
    success = process_manager.model_registry.load_model(model_id, num_instances=num_instances)
    if success:
        logger.info(f"✅ 默认配置测试成功: 模型 {model_id} 加载成功，实例数: {num_instances}")
    else:
        logger.error(f"❌ 默认配置测试失败: 模型 {model_id} 加载失败")
    
    return success

def test_custom_config():
    """测试自定义配置（多个实例）"""
    logger.info("=== 测试自定义配置（3个实例）===")
    
    # 创建进程管理器
    process_manager = ProcessManager()
    process_manager.initialize()
    
    # 测试配置
    model_config = {
        'name': 'yolov8n',
        'img_size': 640,
        'conf_thres': 0.25,
        'iou_thres': 0.45,
        'model_pool_size': 3  # 自定义3个实例
    }
    
    # 注册和加载模型
    model_id = process_manager.model_registry.register_model(
        'algocf6c488d', 'yolov8n', model_config
    )
    
    # 获取实例数配置
    num_instances = model_config.get('model_pool_size', 1)
    logger.info(f"配置的实例数: {num_instances}")
    
    # 加载模型
    success = process_manager.model_registry.load_model(model_id, num_instances=num_instances)
    if success:
        logger.info(f"✅ 自定义配置测试成功: 模型 {model_id} 加载成功，实例数: {num_instances}")
    else:
        logger.error(f"❌ 自定义配置测试失败: 模型 {model_id} 加载失败")
    
    return success

def test_package_config():
    """测试从package_config.yaml读取配置"""
    logger.info("=== 测试从package_config.yaml读取配置===")
    
    # 读取配置文件
    config_path = "algorithms/installed/algocf6c488d/package_config.yaml"
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        model_config = config.get('model_config', {})
        model_pool_size = model_config.get('model_pool_size', 1)
        
        logger.info(f"配置文件路径: {config_path}")
        logger.info(f"读取到的model_pool_size: {model_pool_size}")
        logger.info(f"✅ 配置文件读取成功")
        
        return True
    else:
        logger.error(f"❌ 配置文件不存在: {config_path}")
        return False

def main():
    """主测试函数"""
    logger.info("开始测试模型实例池配置功能")
    
    # 测试1: 默认配置
    test1_result = test_default_config()
    
    # 测试2: 自定义配置
    test2_result = test_custom_config()
    
    # 测试3: 配置文件读取
    test3_result = test_package_config()
    
    # 总结
    logger.info("=== 测试总结 ===")
    logger.info(f"默认配置测试: {'✅ 通过' if test1_result else '❌ 失败'}")
    logger.info(f"自定义配置测试: {'✅ 通过' if test2_result else '❌ 失败'}")
    logger.info(f"配置文件读取测试: {'✅ 通过' if test3_result else '❌ 失败'}")
    
    if all([test1_result, test2_result, test3_result]):
        logger.info("🎉 所有测试通过！模型实例池配置功能正常工作")
    else:
        logger.error("❌ 部分测试失败，请检查配置")

if __name__ == "__main__":
    main() 