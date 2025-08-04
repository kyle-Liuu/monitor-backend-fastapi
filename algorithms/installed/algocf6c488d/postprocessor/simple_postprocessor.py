"""
最简化的后处理器实现
- 只保留核心功能
- 易于理解和维护
- 适合非专业人员使用
"""

import logging
import cv2
import yaml
import os

logger = logging.getLogger(__name__)

class SimplePostprocessor:
    """简化的后处理器"""
    
    def __init__(self, source_id, alg_name, config=None):
        """
        初始化后处理器
        Args:
            source_id: 源ID
            alg_name: 算法名称
            config: 配置字典
        """
        self.source_id = source_id
        self.alg_name = alg_name
        self.config = config or {}
        self.conf_threshold = self.config.get('conf_thres', 0.25)
        
        # 加载标签配置
        self.class2label = {}
        self.label_map = {}
        self.label2color = {}
        self._load_label_config()
        
        logger.info(f"后处理器初始化: {alg_name}")
    
    def _load_label_config(self):
        """加载标签配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'postprocessor.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                
                # 提取标签配置
                model_config = yaml_config.get('model', {}).get('yolov8_model', {}).get('label', {})
                self.class2label = model_config.get('class2label', {})
                self.label_map = model_config.get('label_map', {})
                self.label2color = model_config.get('label2color', {})
                
                logger.info(f"标签配置加载成功: {len(self.class2label)} 个类别")
            else:
                logger.warning(f"配置文件不存在: {config_path}")
        except Exception as e:
            logger.error(f"加载标签配置失败: {e}")
    
    def process(self, model_results, img_shape=None):
        """
        处理后处理
        Args:
            model_results: 模型推理结果列表
            img_shape: 图像尺寸（可选）
        Returns:
            标准化的后处理结果
        """
        try:
            rectangles = []
            
            # 处理每个检测结果
            for result in model_results:
                conf = result.get('conf', 0)
                label_id = result.get('label', -1)
                
                # 过滤低置信度的结果
                if conf < self.conf_threshold:
                    continue
                
                # 过滤不在class2label范围内的结果
                # 注意：YAML解析后键可能是整数类型，需要统一处理
                if label_id not in self.class2label:
                    continue
                
                # 获取标签名称
                label_name = self.class2label.get(label_id, f'unknown_{label_id}')
                
                # 获取中文标签
                chinese_label = self.label_map.get(label_name, label_name)
                
                # 获取颜色
                color = self.label2color.get(chinese_label, [0, 255, 0])  # 默认绿色
                
                rect = {
                    'xyxy': result.get('xyxy', []),
                    'conf': conf,
                    'label': label_name,  # 使用英文标签名
                    'chinese_label': chinese_label,  # 中文标签
                    'color': color
                }
                rectangles.append(rect)
            
            # 返回标准格式
            return {
                'data': {
                    'bbox': {
                        'rectangles': rectangles
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"后处理失败: {e}")
            return {'data': {'bbox': {'rectangles': []}}}
    
    def draw_results(self, image, results):
        """
        在图像上绘制检测结果
        Args:
            image: 输入图像
            results: 检测结果
        Returns:
            绘制了结果的图像
        """
        try:
            # 获取检测数据
            data = results.get('data', {})
            bbox_data = data.get('bbox', {})
            rectangles = bbox_data.get('rectangles', [])
            
            # 绘制每个检测框
            for rect in rectangles:
                xyxy = rect.get('xyxy', [])
                if len(xyxy) == 4:
                    x1, y1, x2, y2 = map(int, xyxy)
                    color = rect.get('color', [0, 255, 0])
                    label = rect.get('label', '')
                    chinese_label = rect.get('chinese_label', label)
                    conf = rect.get('conf', 0)
                    
                    # 绘制矩形框
                    cv2.rectangle(image, (x1, y1), (x2, y2), 
                                (int(color[0]), int(color[1]), int(color[2])), 2)
                    
                    # 绘制标签（显示英文标签名）
                    if label and conf > 0:
                        text = f"{label} {conf:.2f}"
                        cv2.putText(image, text, (x1, y1 - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, 
                                  (int(color[0]), int(color[1]), int(color[2])), 2)
            
            return image
            
        except Exception as e:
            logger.error(f"绘制结果失败: {e}")
            return image


def create_postprocessor(source_id, alg_name, config=None):
    """创建后处理器实例"""
    return SimplePostprocessor(source_id, alg_name, config) 