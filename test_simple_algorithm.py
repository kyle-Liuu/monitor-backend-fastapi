#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化的算法包测试脚本
- 测试简化的YOLOv8算法包
- 验证模型和后处理器是否正常工作
- 适合非专业人员使用
"""

import cv2
import numpy as np
import time
import os
import sys
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入简化的算法包
from algorithms.installed.algocf6c488d.model.simple_yolo import SimpleYOLODetector
from algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor import SimplePostprocessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_simple_algorithm():
    """测试简化的算法包"""
    
    logger.info("开始测试简化的YOLOv8算法包...")
    
    try:
        # 1. 创建模型配置
        model_conf = {
            'args': {
                'img_size': 640,
                'conf_thres': 0.25,
                'iou_thres': 0.45,
                'max_det': 20,
                'model_file': 'yolov8n.pt'
            }
        }
        
        # 2. 创建后处理器配置
        postprocessor_conf = {
            'conf_thres': 0.25
        }
        
        # 3. 创建模型
        logger.info("正在创建模型...")
        model = SimpleYOLODetector('test_detector', model_conf)
        logger.info("模型创建成功")
        
        # 4. 创建后处理器
        logger.info("正在创建后处理器...")
        postprocessor = SimplePostprocessor('test_source', 'test_detector', postprocessor_conf)
        logger.info("后处理器创建成功")
        
        # 5. 加载测试图像
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
        
        # 6. 执行推理
        logger.info("正在执行推理...")
        start_time = time.time()
        results, standard_results = model.infer(test_image)
        inference_time = time.time() - start_time
        logger.info(f"推理完成，耗时: {inference_time:.3f}秒")
        logger.info(f"检测到 {len(standard_results)} 个目标")
        
        # 7. 后处理
        logger.info("正在执行后处理...")
        start_time = time.time()
        processed_results = postprocessor.process(standard_results)
        postprocess_time = time.time() - start_time
        logger.info(f"后处理完成，耗时: {postprocess_time:.3f}秒")
        
        # 8. 绘制结果
        logger.info("正在绘制结果...")
        drawn_image = postprocessor.draw_results(test_image.copy(), processed_results)
        logger.info("结果绘制完成")
        
        # 9. 保存结果图像
        output_path = "test_output_simple.jpg"
        cv2.imwrite(output_path, drawn_image)
        logger.info(f"结果图像已保存到: {output_path}")
        
        # 10. 输出统计信息
        logger.info("\n" + "="*50)
        logger.info("测试结果统计")
        logger.info("="*50)
        logger.info(f"推理时间: {inference_time:.3f}秒")
        logger.info(f"后处理时间: {postprocess_time:.3f}秒")
        logger.info(f"总处理时间: {inference_time + postprocess_time:.3f}秒")
        logger.info(f"检测目标数量: {len(standard_results)}")
        
        # 11. 显示检测结果详情
        if standard_results:
            logger.info("\n检测结果详情:")
            for i, result in enumerate(standard_results):
                xyxy = result.get('xyxy', [])
                conf = result.get('conf', 0)
                label = result.get('label', '')
                logger.info(f"  目标{i+1}: 坐标={xyxy}, 置信度={conf:.3f}, 类别={label}")
        
        # 12. 清理资源
        logger.info("正在清理资源...")
        model.release()
        logger.info("资源清理完成")
        
        logger.info("\n✅ 算法包测试成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ 算法包测试失败: {e}")
        return False

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("简化的YOLOv8算法包测试")
    logger.info("="*60)
    
    # 运行测试
    success = test_simple_algorithm()
    
    if success:
        logger.info("\n🎉 测试完成！算法包工作正常。")
        logger.info("现在可以在 test_cuda_realtime.py 中使用这个算法包了。")
    else:
        logger.error("\n💥 测试失败！请检查错误信息。")
    
    logger.info("="*60)

if __name__ == "__main__":
    main() 