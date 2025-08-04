#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
改进的算法包测试脚本
- 使用算法包管理器
- 支持自动版本选择
- 测试简化版本和标准版本
"""

import cv2
import numpy as np
import time
import os
import sys
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入算法包管理器
from algorithms.installed.algocf6c488d.algorithm_package_manager import get_package_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_algorithm_package():
    """测试算法包"""
    
    logger.info("开始测试改进的YOLOv8算法包...")
    
    try:
        # 1. 获取算法包管理器
        package_manager = get_package_manager()
        
        # 2. 获取算法包信息
        package_info = package_manager.get_package_info()
        logger.info(f"算法包信息: {package_info}")
        
        # 3. 验证算法包
        is_valid, message = package_manager.validate_package()
        if not is_valid:
            logger.error(f"算法包验证失败: {message}")
            return False
        
        logger.info(f"算法包验证通过: {message}")
        
        # 4. 创建模型
        logger.info("正在创建模型...")
        model = package_manager.create_model('test_detector')
        logger.info("模型创建成功")
        
        # 5. 创建后处理器
        logger.info("正在创建后处理器...")
        postprocessor = package_manager.create_postprocessor('test_source', 'test_detector')
        logger.info("后处理器创建成功")
        
        # 6. 加载测试图像
        logger.info("正在加载测试图像...")
        test_image_path = os.path.join(os.path.dirname(__file__), 'bus.jpg')
        if not os.path.exists(test_image_path):
            logger.error(f"测试图像不存在: {test_image_path}")
            return False
        
        test_image = cv2.imread(test_image_path)
        if test_image is None:
            logger.error(f"无法加载测试图像: {test_image_path}")
            return False
        
        logger.info(f"测试图像加载成功，尺寸: {test_image.shape}")
        
        # 7. 执行推理
        logger.info("正在执行推理...")
        start_time = time.time()
        results, standard_results = model.infer(test_image)
        inference_time = time.time() - start_time
        logger.info(f"推理完成，耗时: {inference_time:.3f}秒")
        logger.info(f"检测到 {len(standard_results)} 个目标")
        
        # 8. 后处理
        logger.info("正在执行后处理...")
        start_time = time.time()
        processed_results = postprocessor.process(standard_results)
        postprocess_time = time.time() - start_time
        logger.info(f"后处理完成，耗时: {postprocess_time:.3f}秒")
        
        # 9. 绘制结果
        logger.info("正在绘制结果...")
        drawn_image = postprocessor.draw_results(test_image.copy(), processed_results)
        logger.info("结果绘制完成")
        
        # 10. 保存结果图像
        output_path = "test_output_improved.jpg"
        cv2.imwrite(output_path, drawn_image)
        logger.info(f"结果图像已保存到: {output_path}")
        
        # 11. 输出统计信息
        logger.info("\n" + "="*50)
        logger.info("测试结果统计")
        logger.info("="*50)
        logger.info(f"算法包版本: {package_info['version_type']}")
        logger.info(f"推理时间: {inference_time:.3f}秒")
        logger.info(f"后处理时间: {postprocess_time:.3f}秒")
        logger.info(f"总处理时间: {inference_time + postprocess_time:.3f}秒")
        logger.info(f"检测目标数量: {len(standard_results)}")
        
        # 12. 显示检测结果详情
        if standard_results:
            logger.info("\n检测结果详情:")
            for i, result in enumerate(standard_results):
                xyxy = result.get('xyxy', [])
                conf = result.get('conf', 0)
                label = result.get('label', '')
                logger.info(f"  目标{i+1}: 坐标={xyxy}, 置信度={conf:.3f}, 类别={label}")
        
        # 13. 清理资源
        logger.info("正在清理资源...")
        model.release()
        logger.info("资源清理完成")
        
        logger.info("\n✅ 算法包测试成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 算法包测试失败: {e}")
        return False

def test_version_selection():
    """测试版本选择功能"""
    
    logger.info("\n" + "="*50)
    logger.info("测试版本选择功能")
    logger.info("="*50)
    
    try:
        # 获取算法包管理器
        package_manager = get_package_manager()
        
        # 测试简化版本
        logger.info("测试简化版本...")
        model_simple = package_manager.create_model('simple_model')
        postprocessor_simple = package_manager.create_postprocessor('simple_source', 'simple_alg')
        
        # 测试标准版本（如果可用）
        logger.info("测试标准版本...")
        try:
            # 临时修改配置以强制使用基类
            original_config = package_manager.config.copy()
            package_manager.use_base_class = True
            package_manager.auto_detect = False
            
            model_standard = package_manager.create_model('standard_model')
            postprocessor_standard = package_manager.create_postprocessor('standard_source', 'standard_alg')
            
            logger.info("✅ 标准版本测试成功")
            
            # 恢复配置
            package_manager.config = original_config
            package_manager.use_base_class = original_config.get('use_base_class', False)
            package_manager.auto_detect = original_config.get('auto_detect', True)
            
        except Exception as e:
            logger.info(f"⚠️ 标准版本不可用: {e}")
        
        logger.info("✅ 版本选择测试完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 版本选择测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("改进的YOLOv8算法包测试")
    logger.info("="*60)
    
    # 运行基本测试
    success1 = test_algorithm_package()
    
    # 运行版本选择测试
    success2 = test_version_selection()
    
    if success1 and success2:
        logger.info("\n🎉 所有测试完成！算法包工作正常。")
        logger.info("现在可以在 test_cuda_realtime.py 中使用这个算法包了。")
    else:
        logger.error("\n💥 部分测试失败！请检查错误信息。")
    
    logger.info("="*60)

if __name__ == "__main__":
    main() 