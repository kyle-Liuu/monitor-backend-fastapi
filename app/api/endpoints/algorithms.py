from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Path as PathParam
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import os
import shutil
import zipfile
import tempfile
import json
import uuid
import time
import yaml

from app.db.database import get_db
from app.schemas.algorithm import AlgorithmBase, AlgorithmCreate, AlgorithmUpdate, AlgorithmInDB, AlgorithmResponse
from app.utils.utils import get_current_active_user

router = APIRouter()

# 获取算法列表
@router.get("/", response_model=Dict[str, Any])
def get_algorithms(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """获取算法列表"""
    try:
        query = text("""
            SELECT algo_id, name, version, description, algorithm_type, 
                   path, status, device_type, author, created_at, updated_at
            FROM algorithms
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """)
        
        count_query = text("SELECT COUNT(*) as total FROM algorithms")
        
        result = db.execute(query, {"skip": skip, "limit": limit})
        count_result = db.execute(count_query)
        
        algorithms = result.fetchall()
        total = count_result.scalar_one()
        
        items = []
        for row in algorithms:
            items.append({
                "algo_id": row[0],
                "name": row[1],
                "version": row[2],
                "description": row[3],
                "algorithm_type": row[4],
                "path": row[5],
                "status": row[6],
                "device_type": row[7] if row[7] else "cpu,gpu",
                "author": row[8],
                "created_at": row[9],
                "updated_at": row[10]
            })
        
        return {
            "items": items,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        # 如果数据库查询失败，返回空列表而不是500错误
        return {
            "items": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
            "error": f"获取算法列表失败: {str(e)}"
        }

# 获取单个算法详情
@router.get("/{algo_id}", response_model=Dict[str, Any])
def get_algorithm(
    algo_id: str = PathParam(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """获取单个算法详情"""
    query = text("""
        SELECT algo_id, name, version, description, algorithm_type, 
               path, status, device_type, author, created_at, updated_at
        FROM algorithms
        WHERE algo_id = :algo_id
    """)
    
    result = db.execute(query, {"algo_id": algo_id})
    algorithm = result.fetchone()
    
    if not algorithm:
        raise HTTPException(status_code=404, detail="算法不存在")
    
    return {
        "algo_id": algorithm[0],
        "name": algorithm[1],
        "version": algorithm[2],
        "description": algorithm[3],
        "algorithm_type": algorithm[4],
        "path": algorithm[5],
        "status": algorithm[6],
        "device_type": algorithm[7] if algorithm[7] else "cpu,gpu",
        "author": algorithm[8],
        "created_at": algorithm[9],
        "updated_at": algorithm[10]
    }

# 上传算法包
@router.post("/upload", response_model=Dict[str, Any])
def upload_algorithm(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """上传并安装算法包"""
    try:
        # 保存上传的文件
        upload_dir = get_upload_dir()
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        
        # 保存文件到磁盘
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 处理算法包
        result = process_algorithm_package(file_path, db)
        
        return {
            "success": True,
            "message": f"算法上传并安装成功: {result['name']} v{result['version']}",
            "algorithm": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"算法上传处理失败: {str(e)}")

# 直接注册算法
@router.post("/register_direct", response_model=Dict[str, Any])
def register_algorithm_direct(
    algorithm: AlgorithmCreate,
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """直接注册算法（无需上传文件）"""
    try:
        # 生成唯一ID
        algo_id = f"algo_{uuid.uuid4().hex[:8]}"
        
        # 注册算法
        register_algorithm(
            db,
            algo_id=algo_id,
            name=algorithm.name,
            version=algorithm.version,
            description=algorithm.description,
            algo_type=algorithm.algorithm_type,
            path=algorithm.path,
            status="active"
        )
        
        return {
            "success": True,
            "message": f"算法直接注册成功: {algorithm.name} v{algorithm.version}",
            "algorithm": {
                "algo_id": algo_id,
                "name": algorithm.name,
                "version": algorithm.version,
                "description": algorithm.description,
                "algorithm_type": algorithm.algorithm_type,
                "path": algorithm.path,
                "status": "active"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"算法注册失败: {str(e)}")

# 更新算法状态
@router.put("/{algo_id}/status", response_model=Dict[str, Any])
def update_status(
    status: str,
    algo_id: str = PathParam(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """更新算法状态"""
    try:
        # 验证状态
        if status not in ["active", "inactive", "error"]:
            raise HTTPException(status_code=400, detail="无效的状态值")
        
        # 检查算法是否存在
        query = text("SELECT algo_id FROM algorithms WHERE algo_id = :algo_id")
        result = db.execute(query, {"algo_id": algo_id})
        algorithm = result.fetchone()
        
        if not algorithm:
            raise HTTPException(status_code=404, detail="算法不存在")
        
        # 更新状态
        update_algorithm_status(db, algo_id, status)
        
        return {
            "success": True,
            "message": f"算法状态已更新为 {status}",
            "algo_id": algo_id,
            "status": status
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新算法状态失败: {str(e)}")

# 删除算法
@router.delete("/{algo_id}", response_model=Dict[str, Any])
def delete_algorithm(
    algo_id: str = PathParam(...),
    db: Session = Depends(get_db),
    current_user: Dict = Depends(get_current_active_user)
):
    """删除算法"""
    try:
        # 检查算法是否存在
        query = text("""
            SELECT algo_id, path 
            FROM algorithms 
            WHERE algo_id = :algo_id
        """)
        result = db.execute(query, {"algo_id": algo_id})
        algorithm = result.fetchone()
        
        if not algorithm:
            raise HTTPException(status_code=404, detail="算法不存在")
        
        # 从数据库中删除算法
        delete_query = text("DELETE FROM algorithms WHERE algo_id = :algo_id")
        db.execute(delete_query, {"algo_id": algo_id})
        db.commit()
        
        # 尝试删除算法文件
        try:
            algo_path = algorithm.path
            if algo_path and os.path.exists(algo_path):
                if os.path.isdir(algo_path):
                    shutil.rmtree(algo_path)
                else:
                    os.remove(algo_path)
        except Exception as e:
            # 只记录日志，不中断流程
            print(f"删除算法文件时出错: {str(e)}")
        
        return {
            "success": True,
            "message": "算法已成功删除",
            "algo_id": algo_id
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除算法失败: {str(e)}")


def get_upload_dir():
    """获取算法包上传目录"""
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                              "algorithms", "uploads")
    return upload_dir


def get_install_dir():
    """获取算法安装目录"""
    install_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                              "algorithms", "installed")
    return install_dir


def process_algorithm_package(file_path, db):
    """处理上传的算法包"""
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 解压文件
        if not zipfile.is_zipfile(file_path):
            raise ValueError("上传的文件不是有效的ZIP压缩包")
        
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 检查目录结构
        extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
        if not extracted_dirs:
            raise ValueError("算法包中没有找到有效的目录")
        
        # 选择第一个目录作为算法主目录（或者可以按命名约定寻找特定的目录）
        algo_dir_name = extracted_dirs[0]
        algo_dir = os.path.join(temp_dir, algo_dir_name)
        
        # 检查配置文件是否存在
        model_yaml_path = os.path.join(algo_dir, "model", "model.yaml")
        postproc_yaml_path = os.path.join(algo_dir, "postprocessor", "postprocessor.yaml")
        
        if not os.path.exists(model_yaml_path):
            raise ValueError("缺少必要的算法配置文件: model.yaml")
        if not os.path.exists(postproc_yaml_path):
            raise ValueError("缺少必要的后处理配置文件: postprocessor.yaml")
        
        # 读取配置文件
        with open(model_yaml_path, 'r', encoding='utf-8') as f:
            model_config = yaml.safe_load(f)
        
        with open(postproc_yaml_path, 'r', encoding='utf-8') as f:
            postproc_config = yaml.safe_load(f)
        
        # 检查和提取配置信息
        algo_name = model_config.get("name", algo_dir_name)
        algo_version = model_config.get("version", "1.0.0")
        algo_type = model_config.get("type", "detection")
        algo_description = model_config.get("description", f"Algorithm {algo_name}")
        
        # 生成唯一ID
        algo_id = f"algo_{uuid.uuid4().hex[:8]}"
        
        # 创建安装目录
        install_dir = get_install_dir()
        os.makedirs(install_dir, exist_ok=True)
        algo_install_dir = os.path.join(install_dir, algo_id)
        
        # 如果目标目录已存在，先删除
        if os.path.exists(algo_install_dir):
            shutil.rmtree(algo_install_dir)
        
        # 复制到安装目录
        shutil.copytree(algo_dir, algo_install_dir)
        
        # 注册算法到数据库
        register_algorithm(
            db, 
            algo_id=algo_id, 
            name=algo_name, 
            version=algo_version, 
            description=algo_description,
            algo_type=algo_type, 
            path=algo_install_dir,
            status="active"
        )
        
        # 注：算法管理器会自动检测新注册的算法，无需手动刷新
        
        # 返回注册的算法信息
        return {
            "algo_id": algo_id,
            "name": algo_name,
            "version": algo_version,
            "description": algo_description,
            "type": algo_type,
            "path": algo_install_dir,
            "status": "active"
        }


def register_algorithm(db, algo_id, name, version, description, algo_type, path, status):
    """注册算法到数据库"""
    query = text("""
        INSERT INTO algorithms 
        (algo_id, name, version, description, algorithm_type, path, status, device_type, created_at, updated_at)
        VALUES 
        (:algo_id, :name, :version, :description, :algorithm_type, :path, :status, :device_type, :created_at, :updated_at)
    """)
    
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    
    db.execute(query, {
        "algo_id": algo_id,
        "name": name,
        "version": version,
        "description": description,
        "algorithm_type": algo_type,
        "path": path,
        "status": status,
        "device_type": "cpu,gpu",  # 默认支持cpu和gpu
        "created_at": now,
        "updated_at": now
    })
    
    db.commit()


def update_algorithm_status(db, algo_id, status):
    """更新算法状态"""
    query = text("""
        UPDATE algorithms 
        SET status = :status, updated_at = :updated_at
        WHERE algo_id = :algo_id
    """)
    
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    
    db.execute(query, {
        "algo_id": algo_id,
        "status": status,
        "updated_at": now
    })
    
    db.commit() 