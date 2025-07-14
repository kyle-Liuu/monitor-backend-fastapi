from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.utils.logger import db_logger

# SQLAlchemy异步引擎
db_logger.info("创建数据库引擎")
engine = create_async_engine(settings.SQLITE_URL, echo=False)

# 会话工厂
async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 声明式基类
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖
    """
    async with async_session_factory() as session:
        db_logger.debug("创建数据库会话")
        try:
            yield session
            await session.commit()
            db_logger.debug("提交数据库会话")
        except Exception as e:
            await session.rollback()
            db_logger.error(f"数据库会话出错，回滚: {str(e)}")
            raise
        finally:
            await session.close()
            db_logger.debug("关闭数据库会话")


async def init_db() -> None:
    """
    初始化数据库
    """
    db_logger.info("开始创建数据库表...")
    async with engine.begin() as conn:
        # 创建所有表
        try:
            await conn.run_sync(Base.metadata.create_all)
            db_logger.info("数据库表创建完成")
        except Exception as e:
            db_logger.error(f"创建数据库表时出错: {str(e)}")
            raise 