# 简化的 YOLOv8 算法包

## 📋 简介

这是一个最简化的 YOLOv8 目标检测算法包，专为非专业人员设计，代码简洁易懂。

## 📁 文件结构

```
algocf6c488d/
├── model/                          # 模型目录
│   ├── __init__.py                # 模块初始化
│   ├── simple_yolo.py             # 简化模型（基础版本）
│   ├── simple_yolo_improved.py    # 改进模型（支持基类）
│   ├── model.yaml                 # 模型配置
│   └── yolov8_model/             # 模型权重目录
│       └── yolov8n.pt            # YOLOv8模型文件
├── postprocessor/                  # 后处理目录
│   ├── __init__.py                # 模块初始化
│   ├── simple_postprocessor.py    # 简化后处理器（基础版本）
│   ├── simple_postprocessor_improved.py # 改进后处理器（支持基类）
│   ├── postprocessor.yaml         # 后处理配置
│   └── yolov8_detection.json     # 参数配置
├── algorithm_package_manager.py   # 算法包管理器
├── package_config.yaml           # 算法包配置
└── __init__.py                    # 包初始化
```

## 🚀 快速使用

### 方式一：使用算法包管理器（推荐）

```python
from algorithms.installed.algocf6c488d.algorithm_package_manager import get_package_manager

# 获取算法包管理器
package_manager = get_package_manager()

# 创建模型和后处理器
model = package_manager.create_model('detector')
postprocessor = package_manager.create_postprocessor('source', 'detector')

# 执行检测
results, standard_results = model.infer(image)
processed_results = postprocessor.process(standard_results)
drawn_image = postprocessor.draw_results(image, processed_results)
```

### 方式二：直接导入模块

```python
from algorithms.installed.algocf6c488d.model.simple_yolo import SimpleYOLODetector
from algorithms.installed.algocf6c488d.postprocessor.simple_postprocessor import SimplePostprocessor
```

### 2. 创建模型

```python
# 模型配置
model_conf = {
    'args': {
        'img_size': 640,
        'conf_thres': 0.25,
        'iou_thres': 0.45,
        'max_det': 20,
        'model_file': 'yolov8n.pt'
    }
}

# 创建模型
model = SimpleYOLODetector('yolov8_detector', model_conf)
```

### 3. 创建后处理器

```python
# 后处理器配置
postprocessor_conf = {
    'conf_thres': 0.25
}

# 创建后处理器
postprocessor = SimplePostprocessor('test_source', 'yolov8_detector', postprocessor_conf)
```

### 4. 执行检测

```python
# 读取图像
image = cv2.imread('test.jpg')

# 执行推理
results, standard_results = model.infer(image)

# 后处理
processed_results = postprocessor.process(standard_results)

# 绘制结果
drawn_image = postprocessor.draw_results(image, processed_results)
```

## 📊 输出格式

### 标准化结果格式

```python
[
    {
        'xyxy': [x1, y1, x2, y2],  # 边界框坐标
        'conf': 0.85,              # 置信度
        'label': 0                 # 类别标签
    },
    # ... 更多检测结果
]
```

### 后处理结果格式

```python
{
    'data': {
        'bbox': {
            'rectangles': [
                {
                    'xyxy': [x1, y1, x2, y2],
                    'conf': 0.85,
                    'label': '0',
                    'color': [0, 255, 0]
                }
            ]
        }
    }
}
```

## ⚙️ 配置说明

### model.yaml

```yaml
yolov8_model:
  type: "detection"
  input_size: 640
  supported_devices: ["cpu", "cuda"]
  model_file: "yolov8n.pt"
```

### postprocessor.yaml

```yaml
name: "YOLOv8目标检测"
version: "1.0.0"
description: "简化的YOLOv8目标检测"
conf_threshold: 0.25
```

## 🔧 主要功能

### 算法包管理器 (AlgorithmPackageManager)

- **自动版本选择**: 根据配置自动选择简化版本或标准版本
- **统一接口**: 提供统一的模型和后处理器创建接口
- **配置管理**: 集中管理算法包配置
- **包验证**: 验证算法包的完整性

### 模型类

#### SimpleYOLODetector (简化版本)

- **加载模型**: 自动加载 YOLOv8 模型文件
- **模型预热**: 自动预热，提高首次推理速度
- **推理**: 执行目标检测推理
- **结果转换**: 将结果转换为标准格式

#### StandardYOLODetector (标准版本)

- **继承基类**: 继承 BaseModel，实现标准接口
- **配置驱动**: 支持更灵活的配置参数
- **类型安全**: 提供类型提示和验证

### 后处理器类

#### SimplePostprocessor (简化版本)

- **结果过滤**: 过滤低置信度的检测结果
- **结果格式化**: 将结果格式化为标准输出
- **结果绘制**: 在图像上绘制检测框和标签

#### StandardPostprocessor (标准版本)

- **继承基类**: 继承 BasePostprocessor，实现标准接口
- **高级过滤**: 支持更复杂的过滤策略
- **扩展功能**: 支持更多后处理功能

## 🎯 使用示例

完整的使用示例请参考 `backend/test_cuda_realtime.py` 文件。

## 📝 注意事项

1. **模型文件**: 确保 `yolov8_model/yolov8n.pt` 文件存在
2. **依赖库**: 需要安装 `ultralytics`, `opencv-python`, `torch` 等库
3. **GPU 支持**: 如果有 NVIDIA GPU，会自动使用 CUDA 加速
4. **内存使用**: 模型加载后会占用一定内存，使用完毕后记得释放

## 🆘 常见问题

### Q: 模型加载失败怎么办？

A: 检查模型文件路径是否正确，确保 `yolov8n.pt` 文件存在。

### Q: 推理速度慢怎么办？

A: 确保安装了 CUDA 版本的 PyTorch，并且有 NVIDIA GPU。

### Q: 检测结果不准确怎么办？

A: 可以调整 `conf_thres` 参数来改变置信度阈值。
