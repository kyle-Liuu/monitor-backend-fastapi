# yolov8_detection_optimized.py - 优化版本

import logging
import numpy as np
import cv2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedYOLOv8Postprocessor:
    """YOLOv8后处理器，支持标准化输出、类别过滤、坐标缩放、颜色配置，兼容已反变换坐标"""
    def __init__(self, source_id, alg_name, config=None):
        self.source_id = source_id
        self.alg_name = alg_name
        self.config = config or {}
        self.conf_thres = self.config.get('conf_thres', 0.25)
        self.label_whitelist = self.config.get('label_whitelist', None)  # 允许的类别
        self.color = self.config.get('color', [0, 255, 0])
        logger.info(f"后处理器初始化: {alg_name}")

    def process(self, model_results, img_shape=None):
        """
        Args:
            model_results: 标准化结果列表（已反变换到原分辨率）
            img_shape: (h, w)，用于坐标缩放（可选，通常不需要）
        Returns:
            dict: {'data': {'bbox': {'rectangles': [...]}}}
        """
        rectangles = []
        # 只处理标准化结果列表
        if isinstance(model_results, list) and len(model_results) > 0 and isinstance(model_results[0], dict):
            for obj in model_results:
                conf = obj.get('conf', 0)
                cls = int(obj.get('label', -1))
                if conf >= self.conf_thres and (self.label_whitelist is None or cls in self.label_whitelist):
                    rect = {
                        'xyxy': obj['xyxy'],
                        'conf': conf,
                        'label': str(cls),
                        'color': self.color
                    }
                    # 如果需要再次缩放坐标，可在此处调用 self._scale_xyxy
                    rectangles.append(rect)
        else:
            logger.warning("输入的model_results格式不兼容标准化结果列表")
        return {'data': {'bbox': {'rectangles': rectangles}}}

    def _scale_xyxy(self, xyxy, orig_shape, target_shape):
        # 将xyxy从orig_shape缩放到target_shape
        oh, ow = orig_shape[:2]
        th, tw = target_shape[:2]
        scale_x = tw / ow
        scale_y = th / oh
        x1, y1, x2, y2 = xyxy
        return [x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y]

def create_postprocessor(source_id, alg_name, config=None):
    return OptimizedYOLOv8Postprocessor(source_id, alg_name, config) 