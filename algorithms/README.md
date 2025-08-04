# 算法包管理系统

## 📁 目录结构

```
backend/algorithms/
├── base_classes.py              # 统一基类定义
├── package_manager.py           # 算法包管理器
├── package_algorithm.py         # 算法打包脚本
├── usage_example.py            # 使用示例
├── cleanup.py                  # 清理脚本
├── installed/                  # 已安装算法包
│   └── algocf6c488d/          # YOLOv8算法包
├── uploads/                    # 上传目录
│   └── yolov8_detection.zip   # 上传的算法包
└── registry/                   # 注册目录
    └── __pycache__/           # 缓存文件（可删除）
```

## 🔧 核心文件说明

### 1. `base_classes.py` - 统一基类

- **BaseModel**: 模型基类，定义标准推理接口
- **BasePostprocessor**: 后处理器基类，定义标准后处理接口
- **BaseAlgorithmPackage**: 算法包基类，定义标准包结构
- **ModelInstanceManager**: 模型实例管理器，负责实例生命周期管理

### 2. `package_manager.py` - 包管理器

- **AlgorithmPackage**: 单个算法包管理
- **AlgorithmPackageManager**: 全局包管理器
- 支持包的安装、卸载、验证、发现功能

### 3. `package_algorithm.py` - 打包脚本

- 验证算法目录结构
- 生成标准 ZIP 包
- 支持自定义输出目录

### 4. `usage_example.py` - 使用示例

- 演示完整使用流程
- 展示模型实例管理
- 提供开发参考

## 🚀 算法包上传安装流程

### 1. 算法包结构标准

```
algorithm_package/
├── model/                      # 模型目录
│   ├── model.yaml             # 模型配置
│   ├── model_impl.py          # 模型实现
│   └── weights/               # 模型权重
├── postprocessor/             # 后处理目录
│   ├── postprocessor.yaml     # 后处理配置
│   ├── postprocessor_impl.py  # 后处理实现
│   └── config.json           # 参数配置
└── __init__.py               # 包初始化
```

### 2. 上传流程

1. 用户上传 ZIP 文件到 `uploads/` 目录
2. 系统验证 ZIP 文件完整性
3. 解压到临时目录进行验证
4. 检查算法包结构是否符合标准

### 3. 安装流程

1. 解压算法包到 `installed/` 目录
2. 生成唯一包 ID (如: algocf6c488d)
3. 加载配置文件 (model.yaml, postprocessor.yaml)
4. 验证模型文件完整性
5. 注册到算法包管理器
6. 更新数据库中的算法信息

### 4. 使用流程

```python
# 1. 获取算法包
package = package_manager.get_package("algocf6c488d")

# 2. 创建模型实例
model = package.create_model(model_config)

# 3. 创建后处理器
postprocessor = package.create_postprocessor(postprocessor_config)

# 4. 执行推理
results = model.infer(image)

# 5. 后处理
processed_results = postprocessor.process(results)
```

## 🔄 模型实例管理机制

### 预热机制

- **时机**: 模型实例创建时自动预热
- **目的**: 避免首次推理延迟
- **方式**: 使用随机测试图像进行推理

### 复用机制

- **实例池**: 通过 ModelInstanceManager 管理
- **状态管理**: idle/busy 状态跟踪
- **使用统计**: 记录使用次数和性能指标

### 资源管理

- **自动释放**: 任务完成后自动释放实例
- **内存优化**: 避免重复加载相同模型
- **生命周期**: 完整的创建、使用、释放流程

## 📋 配置文件格式

### model.yaml

```yaml
yolov8_model:
  type: "detection"
  input_size: 640
  supported_devices: ["cpu", "cuda"]
  default_conf_threshold: 0.25
  default_iou_threshold: 0.45
  max_detections: 20
  model_file: "yolov8n.pt"
```

### postprocessor.yaml

```yaml
name: "YOLOv8目标检测"
ch_name: "YOLOv8目标检测"
version: "1.0.0"
description: "基于YOLOv8的目标检测算法"
group_name: "目标检测"
process_time: 10
alert_label: ["person", "car", "truck"]
output_format: "standard"
```

## 🧹 清理建议

### 可以删除的文件

- `registry/__pycache__/` - 缓存文件
- `uploads/` 目录下的旧版本 ZIP 文件（安装后）
- 临时测试文件

### 需要保留的核心文件

- `base_classes.py` - 统一基类（核心）
- `package_manager.py` - 包管理器（核心）
- `package_algorithm.py` - 打包脚本（工具）
- `usage_example.py` - 使用示例（文档）
- `installed/` - 已安装包（数据）
- `uploads/` - 上传目录（功能）

## 🔧 使用示例

```python
# 运行使用示例
cd backend/algorithms
python usage_example.py

# 打包算法
python package_algorithm.py <算法目录> [输出目录]

# 清理目录
python cleanup.py
```
