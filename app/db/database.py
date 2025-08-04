"""
数据库连接管理模块
提供数据库会话和引擎管理功能
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"
# 创建数据库引擎，启用外键约束
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
# 创建会话类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建Base类，用于创建数据库模型类
Base = declarative_base()

def get_db():
    """数据库会话依赖，用于注入到FastAPI路径操作函数中"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 