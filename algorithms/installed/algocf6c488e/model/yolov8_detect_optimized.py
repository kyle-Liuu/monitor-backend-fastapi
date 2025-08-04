# yolov8_detect_optimized.py - 优化版本（包含完整预处理）

import cv2
import numpy as np
import torch
import os
from ultralytics import YOLO
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedYOLOv8Detector:
    """支持动态模型文件、自动预热、常规预处理的YOLOv8检测器，标准化输出，支持坐标反变换"""
    default_args = {
        'img_size': 640,
        'conf_thres': 0.25,
        'iou_thres': 0.45,
        'max_det': 20,
        'model_file': 'yolov8n.pt',
    }

    def __init__(self, name, conf):
        self.name = name
        self.conf = conf
        self.status = False
        self.model = None
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        logger.info(f"使用设备: {self.device}")
        # 加载参数
        self._load_args(conf.get('args', {}))
        # 加载模型
        model_path = os.path.join(os.path.dirname(__file__), 'yolov8_model', self.model_file)
        if not os.path.exists(model_path):
            logger.error(f"模型文件未找到: {model_path}")
            return
        self.model = YOLO(model_path)
        self.status = True
        logger.info(f"YOLOv8权重加载完成: {self.model_file}")
        self._warmup()

    def _load_args(self, args):
        for k, v in self.default_args.items():
            setattr(self, k, args.get(k, v))

    def _warmup(self):
        try:
            dummy = np.random.randint(0, 255, (self.img_size, self.img_size, 3), dtype=np.uint8)
            _ = self.model(dummy, conf=self.conf_thres, iou=self.iou_thres, device=self.device, max_det=1)
            logger.info("模型预热完成")
        except Exception as e:
            logger.warning(f"模型预热失败: {e}")

    def _preprocess(self, image):
        if image is None or image.size == 0:
            raise ValueError("输入图像为空")
        # BGR转RGB
        if image.shape[-1] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image
        # letterbox到img_size，返回缩放信息
        img_padded, ratio, padw, padh = self._letterbox(img_rgb, (self.img_size, self.img_size))
        return img_padded, ratio, padw, padh, img_rgb.shape[:2]

    def _letterbox(self, img, new_shape=(640, 640), color=(114, 114, 114)):
        shape = img.shape[:2]  # current shape [height, width]
        ratio = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
        new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))
        img_resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)
        dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
        dw /= 2
        dh /= 2
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        img_padded = cv2.copyMakeBorder(img_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
        return img_padded, ratio, left, top

    def infer(self, data, **kwargs):
        """
        目标检测
        Args:
            data: 图像数据，ndarray类型，BGR格式
        Returns: ultralytics原始结果对象和标准化结果列表（已映射回原分辨率）
        """
        if not self.status:
            return [], []
        try:
            img_padded, ratio, padw, padh, orig_shape = self._preprocess(data)
            results = self.model(
                img_padded,
                conf=self.conf_thres,
                iou=self.iou_thres,
                device=self.device,
                max_det=self.max_det
            )
            # 标准化输出，做坐标反变换
            std_results = self._to_std_results(results, ratio, padw, padh, orig_shape)
            return results, std_results
        except Exception as e:
            logger.error(f"推理失败: {e}")
            return [], []

    def _to_std_results(self, results, ratio, padw, padh, orig_shape):
        std_results = []
        oh, ow = orig_shape
        if isinstance(results, list) and len(results) > 0 and hasattr(results[0], 'boxes'):
            boxes = results[0].boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                # 坐标反变换到原图
                x1 = max((x1 - padw) / ratio, 0)
                y1 = max((y1 - padh) / ratio, 0)
                x2 = min((x2 - padw) / ratio, ow)
                y2 = min((y2 - padh) / ratio, oh)
                std_results.append({
                    'xyxy': [x1, y1, x2, y2],
                    'conf': conf,
                    'label': str(cls)
                })
        return std_results

    def release(self):
        pass

def create_model(name, conf):
    return OptimizedYOLOv8Detector(name, conf) 