#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
预处理配置文件
- 根据性能测试结果提供不同场景的预处理配置
- 包含实时应用、高精度应用和平衡配置
"""

# 实时应用配置 - 最低延迟 (<50ms)
REALTIME_CONFIG = {
    'preprocess_mode': 'crop',      # 最快的方法 (1.80ms)
    'auto_contrast': False,         # 关闭以节省时间 (123.10ms)
    'blur_detection': True,         # 启用模糊检测 (19.00ms)
    'normalize': True,              # 启用归一化
    'img_size': 640,                # 图像大小
    'half_precision': True,         # 使用FP16加速
    'enable_cuda_graph': True,      # 启用CUDA图优化
    'warmup_frames': 10,            # 预热帧数
}

# 高精度应用配置 - 高检测精度 (>100ms)
HIGH_PRECISION_CONFIG = {
    'preprocess_mode': 'letterbox', # 保持宽高比 (3.21ms)
    'auto_contrast': True,          # 启用对比度增强 (123.10ms)
    'blur_detection': True,         # 启用模糊检测 (19.00ms)
    'normalize': True,              # 启用归一化
    'img_size': 640,                # 图像大小
    'half_precision': True,         # 使用FP16加速
    'enable_cuda_graph': True,      # 启用CUDA图优化
    'warmup_frames': 10,            # 预热帧数
}

# 平衡配置 - 平衡延迟和精度 (50-100ms)
BALANCED_CONFIG = {
    'preprocess_mode': 'resize',    # 平衡方法 (2.80ms)
    'auto_contrast': False,         # 可选启用 (123.10ms)
    'blur_detection': True,         # 启用模糊检测 (19.00ms)
    'normalize': True,              # 启用归一化
    'img_size': 640,                # 图像大小
    'half_precision': True,         # 使用FP16加速
    'enable_cuda_graph': True,      # 启用CUDA图优化
    'warmup_frames': 10,            # 预热帧数
}

# 低端设备配置 - 适用于CPU或低端GPU
LOW_END_CONFIG = {
    'preprocess_mode': 'resize',    # 平衡方法 (2.80ms)
    'auto_contrast': False,         # 关闭以节省时间 (123.10ms)
    'blur_detection': False,        # 关闭以节省时间 (19.00ms)
    'normalize': True,              # 启用归一化
    'img_size': 416,                # 降低图像大小以提高速度
    'half_precision': False,        # CPU不支持FP16
    'enable_cuda_graph': False,     # CPU不支持CUDA图
    'warmup_frames': 5,             # 减少预热帧数
}

# 高端设备配置 - 适用于高端GPU (RTX 3080+)
HIGH_END_CONFIG = {
    'preprocess_mode': 'letterbox', # 保持宽高比 (3.21ms)
    'auto_contrast': True,          # 启用对比度增强 (123.10ms)
    'blur_detection': True,         # 启用模糊检测 (19.00ms)
    'normalize': True,              # 启用归一化
    'img_size': 1280,               # 提高图像大小以提高精度
    'half_precision': True,         # 使用FP16加速
    'enable_cuda_graph': True,      # 启用CUDA图优化
    'warmup_frames': 20,            # 增加预热帧数
    'batch_size': 4,                # 使用批处理
    'enable_tensorrt': True,        # 启用TensorRT
}

# 根据设备类型和延迟要求获取配置
def get_config(device_type='cuda', latency_requirement='balanced'):
    """
    根据设备类型和延迟要求获取预处理配置
    
    Args:
        device_type: 设备类型，'cuda'或'cpu'
        latency_requirement: 延迟要求，'realtime'、'balanced'或'high_precision'
    
    Returns:
        预处理配置字典
    """
    if device_type == 'cpu':
        return LOW_END_CONFIG
    
    if latency_requirement == 'realtime':
        return REALTIME_CONFIG
    elif latency_requirement == 'high_precision':
        return HIGH_PRECISION_CONFIG
    else:  # balanced
        return BALANCED_CONFIG

# 配置说明
CONFIG_DESCRIPTION = {
    'preprocess_mode': '图像尺寸调整方法: letterbox(保持宽高比)、resize(简单缩放)、crop(中心裁剪)',
    'auto_contrast': '自动对比度增强: 使用CLAHE提升图像对比度，提高检测精度但增加处理时间',
    'blur_detection': '模糊检测: 检测并警告模糊图像，可用于过滤低质量帧',
    'normalize': '归一化: 将像素值归一化到[0,1]范围',
    'img_size': '图像大小: 模型输入尺寸，较大尺寸提高精度但降低速度',
    'half_precision': 'FP16精度: 使用半精度浮点数加速推理，仅GPU支持',
    'enable_cuda_graph': 'CUDA图优化: 使用CUDA图加速推理，仅GPU支持',
    'warmup_frames': '预热帧数: 模型预热的帧数，提高首次推理速度',
    'batch_size': '批处理大小: 批量处理的帧数，提高吞吐量但可能增加延迟',
    'enable_tensorrt': 'TensorRT加速: 使用TensorRT加速推理，需要额外安装',
}

if __name__ == "__main__":
    # 打印配置说明
    print("预处理配置说明:")
    for key, desc in CONFIG_DESCRIPTION.items():
        print(f"- {key}: {desc}")
    
    print("\n实时应用配置:")
    for key, value in REALTIME_CONFIG.items():
        print(f"- {key}: {value}")
    
    print("\n高精度应用配置:")
    for key, value in HIGH_PRECISION_CONFIG.items():
        print(f"- {key}: {value}")
    
    print("\n平衡配置:")
    for key, value in BALANCED_CONFIG.items():
        print(f"- {key}: {value}") 