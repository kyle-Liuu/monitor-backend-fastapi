"""
唯一ID生成器
- 生成不同资源类型的唯一标识
"""

import random
import string
import uuid
import time

def generate_unique_id(prefix: str = None, length: int = 7) -> str:
    """
    生成唯一ID
    
    Args:
        prefix: 前缀，如"user"、"stream"等
        length: 随机部分长度，默认7位
        
    Returns:
        唯一ID字符串
    """
    # 确保前缀有效
    if not prefix:
        prefix = "id"
        
    # 生成随机字符部分（包括数字和字母）
    chars = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    
    return f"{prefix}{random_part}"

def generate_uuid() -> str:
    """
    生成UUID
    
    Returns:
        UUID字符串
    """
    return str(uuid.uuid4())

def generate_timestamp_id(prefix: str = None) -> str:
    """
    生成基于时间戳的ID
    
    Args:
        prefix: 前缀，如"task"、"alarm"等
        
    Returns:
        基于时间戳的唯一ID
    """
    # 确保前缀有效
    if not prefix:
        prefix = "id"
        
    # 获取当前时间戳（毫秒）
    timestamp = int(time.time() * 1000)
    
    # 生成3位随机数
    random_part = ''.join(random.choice(string.digits) for _ in range(3))
    
    return f"{prefix}{timestamp}{random_part}" 