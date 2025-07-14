import asyncio
import logging
import os
import sqlite3

from sqlalchemy.ext.asyncio import create_async_engine
from app.db.database import Base
from app.initial_data import init as init_data

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库文件路径
DB_FILE = "app.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_FILE)


async def reset_db() -> None:
    """
    重置数据库
    1. 删除现有数据库文件
    2. 创建新的数据库文件
    3. 创建所有表
    4. 导入初始数据
    """
    try:
        logger.info("开始重置数据库...")
        
        # 删除现有数据库文件（如果存在）
        if os.path.exists(DB_PATH):
            logger.info(f"删除现有数据库文件: {DB_PATH}")
            os.remove(DB_PATH)
        
        # 创建空的SQLite数据库文件
        logger.info("创建新的数据库文件")
        conn = sqlite3.connect(DB_PATH)
        conn.close()
        
        # 创建异步引擎
        logger.info("创建数据库表")
        engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", echo=False)
        
        # 创建所有表
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # 导入初始数据
        logger.info("导入初始数据")
        await init_data()
        
        logger.info("数据库重置成功!")
    except Exception as e:
        logger.error(f"重置数据库时出错: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(reset_db())
