"""
YOLOv8统一后处理器实现
- 继承BasePostprocessor基类
- 实现标准化的后处理接口
- 支持结果过滤和格式化
"""

import logging
import numpy as np
import cv2
from typing import Dict, List, Any, Optional, Tuple

# 导入基类
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from base_classes import BasePostprocessor

logger = logging.getLogger(__name__)

class YOLOv8UnifiedPostprocessor(BasePostprocessor):
    """YOLOv8统一后处理器实现"""
    
    def __init__(self, postprocessor_config: Dict[str, Any]):
        """
        初始化YOLOv8后处理器
        Args:
            postprocessor_config: 后处理器配置字典
        """
        # 设置默认配置
        default_config = {
            'conf_threshold': 0.25,
            'label_whitelist': None,  # 允许的类别列表
            'color': [0, 255, 0],     # 默认绘制颜色
            'draw_bbox': True,        # 是否绘制边界框
            'draw_label': True,       # 是否绘制标签
            'draw_conf': True,        # 是否绘制置信度
            'output_format': 'standard'  # 输出格式
        }
        
        # 合并配置
        merged_config = {**default_config, **postprocessor_config}
        super().__init__(merged_config)
    
    def process(self, model_results: List[Dict], image_shape: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        处理后处理
        Args:
            model_results: 模型推理结果列表（标准化格式）
            image_shape: 图像尺寸 (height, width)
        Returns:
            标准化的后处理结果
        """
        try:
            # 过滤结果
            filtered_results = self.filter_results(model_results)
            
            # 格式化输出
            if self.config.get('output_format') == 'standard':
                return self._format_standard_output(filtered_results)
            else:
                return self._format_custom_output(filtered_results)
                
        except Exception as e:
            logger.error(f"后处理失败: {e}")
            return {'data': {'bbox': {'rectangles': []}}}
    
    def _format_standard_output(self, filtered_results: List[Dict]) -> Dict[str, Any]:
        """
        格式化标准输出
        Args:
            filtered_results: 过滤后的结果
        Returns:
            标准输出格式
        """
        rectangles = []
        
        for result in filtered_results:
            rect = {
                'xyxy': result.get('xyxy', []),
                'conf': result.get('conf', 0.0),
                'label': str(result.get('label', -1)),
                'color': self.color,
                'bbox': result.get('bbox', [])  # [x, y, w, h]
            }
            rectangles.append(rect)
        
        return {
            'data': {
                'bbox': {
                    'rectangles': rectangles
                }
            }
        }
    
    def _format_custom_output(self, filtered_results: List[Dict]) -> Dict[str, Any]:
        """
        格式化自定义输出
        Args:
            filtered_results: 过滤后的结果
        Returns:
            自定义输出格式
        """
        return {
            'detections': filtered_results,
            'count': len(filtered_results),
            'metadata': {
                'conf_threshold': self.conf_threshold,
                'label_whitelist': self.label_whitelist,
                'color': self.color
            }
        }
    
    def draw_results(self, image: np.ndarray, results: List[Dict]) -> np.ndarray:
        """
        在图像上绘制检测结果
        Args:
            image: 输入图像
            results: 检测结果
        Returns:
            绘制了结果的图像
        """
        if not self.config.get('draw_bbox', True):
            return image
        
        try:
            img_draw = image.copy()
            
            for result in results:
                # 获取边界框坐标
                xyxy = result.get('xyxy', [])
                if len(xyxy) != 4:
                    continue
                
                x1, y1, x2, y2 = map(int, xyxy)
                conf = result.get('conf', 0.0)
                label = result.get('label', 'unknown')
                
                # 绘制边界框
                cv2.rectangle(img_draw, (x1, y1), (x2, y2), self.color, 2)
                
                # 绘制标签和置信度
                if self.config.get('draw_label', True) or self.config.get('draw_conf', True):
                    text_parts = []
                    
                    if self.config.get('draw_label', True):
                        text_parts.append(f"{label}")
                    
                    if self.config.get('draw_conf', True):
                        text_parts.append(f"{conf:.2f}")
                    
                    text = " ".join(text_parts)
                    
                    # 计算文本位置
                    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                    text_x = x1
                    text_y = y1 - 10 if y1 - 10 > text_size[1] else y1 + text_size[1]
                    
                    # 绘制文本背景
                    cv2.rectangle(img_draw, 
                                (text_x, text_y - text_size[1] - 5),
                                (text_x + text_size[0], text_y + 5),
                                self.color, -1)
                    
                    # 绘制文本
                    cv2.putText(img_draw, text, (text_x, text_y),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            return img_draw
            
        except Exception as e:
            logger.error(f"绘制结果失败: {e}")
            return image
    
    def get_statistics(self, results: List[Dict]) -> Dict[str, Any]:
        """
        获取检测统计信息
        Args:
            results: 检测结果
        Returns:
            统计信息
        """
        try:
            # 按类别统计
            label_counts = {}
            total_conf = 0.0
            
            for result in results:
                label = result.get('label', -1)
                conf = result.get('conf', 0.0)
                
                label_counts[label] = label_counts.get(label, 0) + 1
                total_conf += conf
            
            return {
                'total_detections': len(results),
                'label_counts': label_counts,
                'average_confidence': total_conf / len(results) if results else 0.0,
                'max_confidence': max([r.get('conf', 0.0) for r in results]) if results else 0.0,
                'min_confidence': min([r.get('conf', 0.0) for r in results]) if results else 0.0
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}


def create_postprocessor(postprocessor_config: Dict[str, Any]) -> YOLOv8UnifiedPostprocessor:
    """
    创建YOLOv8后处理器实例
    Args:
        postprocessor_config: 后处理器配置
    Returns:
        YOLOv8后处理器实例
    """
    return YOLOv8UnifiedPostprocessor(postprocessor_config) 