from datetime import datetime, timedelta
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BlacklistedToken
from app.utils.logger import app_logger


async def cleanup_expired_blacklisted_tokens(db: AsyncSession) -> None:
    """
    清理过期的黑名单令牌
    """
    try:
        # 计算30天前的时间
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # 删除30天前的令牌
        await db.execute(
            BlacklistedToken.__table__.delete().where(
                BlacklistedToken.created_at < thirty_days_ago
            )
        )
        await db.commit()
        
        app_logger.info("已清理过期的黑名单令牌")
    except Exception as e:
        app_logger.error(f"清理黑名单令牌时出错: {e}")
        await db.rollback()


async def schedule_token_cleanup(db_getter):
    """
    定时清理过期的黑名单令牌
    """
    try:
        while True:
            try:
                # 每天运行一次
                await asyncio.sleep(86400)  # 24小时 = 86400秒
                
                # 获取数据库会话
                async with db_getter() as db:
                    await cleanup_expired_blacklisted_tokens(db)
                    
            except asyncio.CancelledError:
                # 处理取消信号
                app_logger.info("令牌清理任务收到取消信号")
                raise  # 重新抛出，以便完成取消过程
            except Exception as e:
                app_logger.error(f"定时清理黑名单令牌任务出错: {e}")
                # 出错后等待1小时再重试
                await asyncio.sleep(3600)
    except asyncio.CancelledError:
        app_logger.info("令牌清理任务已取消")
        # 正常退出 