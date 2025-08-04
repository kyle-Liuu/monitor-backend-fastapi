#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
算法打包脚本，用于将算法目录打包为ZIP文件
使用方法：python package_algorithm.py <算法目录> [输出目录]
适配新的算法结构：模型+后处理分离的结构
"""

import os
import sys
import zipfile
import yaml
import json
import argparse
from pathlib import Path
import shutil

def validate_algorithm_dir(algo_dir):
    """验证算法目录结构"""
    # 检查必须的目录结构
    required_dirs = ["model", "postprocessor"]
    for d in required_dirs:
        if not (algo_dir / d).exists() or not (algo_dir / d).is_dir():
            return False, f"缺少必需目录: {d}"
    
    # 检查模型目录必须文件
    model_dir = algo_dir / "model"
    model_required_files = ["yolov8_detect.py", "model.yaml"]
    for file in model_required_files:
        if not (model_dir / file).exists():
            return False, f"缺少必需文件: model/{file}"
    
    # 检查模型权重目录
    model_weight_dir = model_dir / "yolov8_model"
    if not model_weight_dir.exists() or not model_weight_dir.is_dir():
        return False, f"缺少模型权重目录: model/yolov8_model"
    
    # 检查模型权重文件
    weight_files = list(model_weight_dir.glob("*.pt"))
    if not weight_files:
        return False, f"模型权重目录中缺少.pt文件"
    
    # 检查后处理目录必须文件
    postprocessor_dir = algo_dir / "postprocessor"
    processor_required_files = ["postprocessor.yaml"]
    for file in processor_required_files:
        if not (postprocessor_dir / file).exists():
            return False, f"缺少必需文件: postprocessor/{file}"
    
    # 检查后处理py文件
    # 从postprocessor.yaml获取后处理器名称
    try:
        with open(postprocessor_dir / "postprocessor.yaml", "r", encoding="utf-8") as f:
            processor_config = yaml.safe_load(f)
            processor_name = processor_config.get("name", "yolov8_detection")
            processor_file = f"{processor_name}.py"
            
            if not (postprocessor_dir / processor_file).exists():
                return False, f"缺少后处理文件: postprocessor/{processor_file}"
    except Exception as e:
        return False, f"读取后处理配置失败: {e}"
    
    # 验证model.yaml
    try:
        with open(model_dir / "model.yaml", "r", encoding="utf-8") as f:
            model_config = yaml.safe_load(f)
            if not isinstance(model_config, dict) or not model_config:
                return False, "模型配置文件格式错误"
            
            # 检查是否有有效的模型类型键
            if not model_config or not next(iter(model_config.keys()), None):
                return False, "模型配置文件缺少模型类型"
    except Exception as e:
        return False, f"读取模型配置失败: {e}"
    
    return True, "算法目录验证通过"

def package_algorithm(algo_dir, output_dir=None):
    """打包算法目录为ZIP文件"""
    algo_dir = Path(algo_dir).resolve()
    
    # 验证算法目录
    valid, message = validate_algorithm_dir(algo_dir)
    if not valid:
        print(f"错误: {message}")
        return False
    
    # 读取配置获取算法名称和版本
    postprocessor_yaml = algo_dir / "postprocessor" / "postprocessor.yaml"
    with open(postprocessor_yaml, "r", encoding="utf-8") as f:
        processor_config = yaml.safe_load(f)
    
    algo_name = processor_config.get("name", "unknown_algorithm")
    algo_version = processor_config.get("version", "1.0.0")
    
    # 确定输出目录
    if output_dir is None:
        output_dir = Path.cwd()
    else:
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # 构建ZIP文件名
    zip_filename = f"{algo_name}_v{algo_version}.zip"
    zip_path = output_dir / zip_filename
    
    # 创建临时目录
    temp_dir = Path(f"temp_{algo_name}_{algo_version}")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # 复制算法文件到临时目录
        for item in algo_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, temp_dir)
            elif item.is_dir():
                shutil.copytree(item, temp_dir / item.name)
        
        # 创建一个空的__init__.py文件
        init_py = temp_dir / "__init__.py"
        if not init_py.exists():
            with open(init_py, "w", encoding="utf-8") as f:
                f.write('"""Package initialization file"""\n')
        
        # 确保model和postprocessor目录中都有__init__.py
        for subdir in ["model", "postprocessor"]:
            subdir_init = temp_dir / subdir / "__init__.py"
            if not subdir_init.exists():
                with open(subdir_init, "w", encoding="utf-8") as f:
                    f.write(f'"""Package initialization file for {subdir}"""\n')
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_dir)
                    zipf.write(file_path, arcname)
        
        print(f"算法包已创建: {zip_path}")
        return True
    
    except Exception as e:
        print(f"打包失败: {e}")
        return False
    
    finally:
        # 清理临时目录
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="打包算法目录为ZIP文件 (新算法结构)")
    parser.add_argument("algo_dir", help="算法目录路径")
    parser.add_argument("output_dir", nargs="?", default=None, help="输出目录路径（可选）")
    
    args = parser.parse_args()
    
    package_algorithm(args.algo_dir, args.output_dir)

if __name__ == "__main__":
    main() 