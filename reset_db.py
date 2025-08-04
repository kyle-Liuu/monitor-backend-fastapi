import logging
import os
import sqlite3
import sys
from pathlib import Path

from sqlalchemy import create_engine
from app.db.database import Base, engine
from app.initial_data import init as init_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 数据库文件路径
DB_FILE = "app.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_FILE)


def backup_existing_db():
    """备份现有数据库"""
    if os.path.exists(DB_PATH):
        backup_path = f"{DB_PATH}.backup"
        try:
            import shutil
            shutil.copy2(DB_PATH, backup_path)
            logger.info(f"现有数据库已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"备份数据库失败: {e}")
            return None
    return None


def reset_db() -> None:
    """
    重置数据库
    1. 备份现有数据库文件（如果存在）
    2. 删除现有数据库文件
    3. 创建新的数据库文件
    4. 创建所有表
    5. 导入初始数据
    6. 验证数据库完整性
    """
    try:
        logger.info("=" * 50)
        logger.info("开始重置数据库...")
        logger.info("=" * 50)
        
        # 备份现有数据库
        backup_path = backup_existing_db()
    
        # 删除现有数据库文件（如果存在）
        if os.path.exists(DB_PATH):
            logger.info(f"删除现有数据库文件: {DB_PATH}")
            os.remove(DB_PATH)
        
        # 创建空的SQLite数据库文件
        logger.info("创建新的数据库文件")
        conn = sqlite3.connect(DB_PATH)
        conn.close()
        
        # 创建所有表
        logger.info("创建数据库表...")
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建完成")
        
        # 验证表创建
        logger.info("验证数据库表结构...")
        verify_database_tables()
        
        # 导入初始数据
        logger.info("导入初始数据...")
        init_data()
        logger.info("初始数据导入完成")
        
        # 验证数据完整性
        logger.info("验证数据完整性...")
        verify_data_integrity()
        
        logger.info("=" * 50)
        logger.info("数据库重置成功!")
        logger.info("=" * 50)
        
        if backup_path:
            logger.info(f"原数据库已备份到: {backup_path}")
            
    except Exception as e:
        logger.error(f"重置数据库时出错: {str(e)}")
        logger.error(f"错误详情: {sys.exc_info()}")
        raise


def verify_database_tables():
    """验证数据库表是否正确创建"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = [
            'users', 'roles', 'blacklisted_tokens', 'menus', 
            'organizations', 'organization_bindings', 'streams', 
            'algorithms', 'tasks', 'alarms', 'model_instances', 'system_configs'
        ]
        
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            logger.error(f"缺少以下表: {missing_tables}")
            raise Exception(f"数据库表创建不完整: {missing_tables}")
        else:
            logger.info("所有数据库表创建成功")
            
        # 验证字段名
        verify_table_columns(cursor)
            
        conn.close()
        
    except Exception as e:
        logger.error(f"验证数据库表失败: {e}")
        raise


def verify_table_columns(cursor):
    """验证表字段名是否正确"""
    try:
        # 验证roles表字段
        cursor.execute("PRAGMA table_info(roles)")
        role_columns = [row[1] for row in cursor.fetchall()]
        if 'role_id' not in role_columns:
            logger.error("roles表缺少role_id字段")
            raise Exception("roles表字段名不正确")
        
        # 验证organizations表字段
        cursor.execute("PRAGMA table_info(organizations)")
        org_columns = [row[1] for row in cursor.fetchall()]
        if 'org_id' not in org_columns:
            logger.error("organizations表缺少org_id字段")
            raise Exception("organizations表字段名不正确")
        
        # 验证organization_bindings表字段
        cursor.execute("PRAGMA table_info(organization_bindings)")
        binding_columns = [row[1] for row in cursor.fetchall()]
        if 'binding_id' not in binding_columns:
            logger.error("organization_bindings表缺少binding_id字段")
            raise Exception("organization_bindings表字段名不正确")
        
        # 验证streams表字段
        cursor.execute("PRAGMA table_info(streams)")
        stream_columns = [row[1] for row in cursor.fetchall()]
        if 'stream_id' not in stream_columns:
            logger.error("streams表缺少stream_id字段")
            raise Exception("streams表字段名不正确")
        
        # 验证algorithms表字段
        cursor.execute("PRAGMA table_info(algorithms)")
        algo_columns = [row[1] for row in cursor.fetchall()]
        if 'algo_id' not in algo_columns:
            logger.error("algorithms表缺少algo_id字段")
            raise Exception("algorithms表字段名不正确")
        
        # 验证tasks表字段
        cursor.execute("PRAGMA table_info(tasks)")
        task_columns = [row[1] for row in cursor.fetchall()]
        if 'task_id' not in task_columns:
            logger.error("tasks表缺少task_id字段")
            raise Exception("tasks表字段名不正确")
        
        # 验证alarms表字段
        cursor.execute("PRAGMA table_info(alarms)")
        alarm_columns = [row[1] for row in cursor.fetchall()]
        if 'alarm_id' not in alarm_columns:
            logger.error("alarms表缺少alarm_id字段")
            raise Exception("alarms表字段名不正确")
        
        # 验证model_instances表字段
        cursor.execute("PRAGMA table_info(model_instances)")
        instance_columns = [row[1] for row in cursor.fetchall()]
        if 'instance_id' not in instance_columns:
            logger.error("model_instances表缺少instance_id字段")
            raise Exception("model_instances表字段名不正确")
        
        # 验证system_configs表字段
        cursor.execute("PRAGMA table_info(system_configs)")
        config_columns = [row[1] for row in cursor.fetchall()]
        if 'config_id' not in config_columns:
            logger.error("system_configs表缺少config_id字段")
            raise Exception("system_configs表字段名不正确")
        
        logger.info("所有表字段名验证通过")
        
    except Exception as e:
        logger.error(f"验证表字段失败: {e}")
        raise


def verify_data_integrity():
    """验证数据完整性"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查默认用户
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        logger.info(f"用户数量: {user_count}")
        
        # 检查角色数据
        cursor.execute("SELECT COUNT(*) FROM roles")
        role_count = cursor.fetchone()[0]
        logger.info(f"角色数量: {role_count}")
        
        # 检查组织数据
        cursor.execute("SELECT COUNT(*) FROM organizations")
        org_count = cursor.fetchone()[0]
        logger.info(f"组织数量: {org_count}")
        
        # 检查组织绑定数据
        cursor.execute("SELECT COUNT(*) FROM organization_bindings")
        binding_count = cursor.fetchone()[0]
        logger.info(f"组织绑定数量: {binding_count}")
        
        # 检查默认菜单
        cursor.execute("SELECT COUNT(*) FROM menus")
        menu_count = cursor.fetchone()[0]
        logger.info(f"菜单数量: {menu_count}")
        
        # 检查系统配置
        cursor.execute("SELECT COUNT(*) FROM system_configs")
        config_count = cursor.fetchone()[0]
        logger.info(f"系统配置数量: {config_count}")
        
        # 检查视频流
        cursor.execute("SELECT COUNT(*) FROM streams")
        stream_count = cursor.fetchone()[0]
        logger.info(f"视频流数量: {stream_count}")
        
        # 检查算法
        cursor.execute("SELECT COUNT(*) FROM algorithms")
        algo_count = cursor.fetchone()[0]
        logger.info(f"算法数量: {algo_count}")
        
        # 检查模型实例
        cursor.execute("SELECT COUNT(*) FROM model_instances")
        instance_count = cursor.fetchone()[0]
        logger.info(f"模型实例数量: {instance_count}")
        
        conn.close()
        
        if user_count == 0:
            logger.warning("未找到默认用户数据")
        if role_count == 0:
            logger.warning("未找到默认角色数据")
        if org_count == 0:
            logger.warning("未找到默认组织数据")
        if menu_count == 0:
            logger.warning("未找到默认菜单数据")
        if stream_count == 0:
            logger.warning("未找到默认视频流数据")
        if algo_count == 0:
            logger.warning("未找到默认算法数据")
        if instance_count == 0:
            logger.warning("未找到默认模型实例数据")
            
        logger.info("数据完整性验证完成")
        
    except Exception as e:
        logger.error(f"验证数据完整性失败: {e}")
        raise


def cleanup_temp_files():
    """清理临时文件"""
    try:
        temp_dirs = ['temp_frames', 'output', 'logs']
        for temp_dir in temp_dirs:
            temp_path = os.path.join(os.path.dirname(__file__), temp_dir)
            if os.path.exists(temp_path):
                import shutil
                shutil.rmtree(temp_path)
                logger.info(f"清理临时目录: {temp_dir}")
                
        # 清理日志文件
        log_files = ['*.log', '*.tmp']
        for pattern in log_files:
            import glob
            for log_file in glob.glob(os.path.join(os.path.dirname(__file__), pattern)):
                os.remove(log_file)
                logger.info(f"清理日志文件: {log_file}")
                
    except Exception as e:
        logger.warning(f"清理临时文件失败: {e}")


if __name__ == "__main__":
    try:
        # 清理临时文件
        cleanup_temp_files()
        
        # 重置数据库
        reset_db()
        
        print("\n" + "=" * 50)
        print("数据库重置成功!")
        print("默认用户信息:")
        print("  超级管理员: super (密码: 123456) [角色: R_SUPER]")
        print("  管理员: admin (密码: 123456) [角色: R_ADMIN]")
        print("  普通用户: user (密码: 123456) [角色: R_USER]")
        print("\n默认数据:")
        print("  - 3个系统角色 (R_SUPER, R_ADMIN, R_USER)")
        print("  - 示例组织结构 (总部->A栋/B栋)")
        print("  - 完整菜单权限配置")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n数据库重置失败: {e}")
        sys.exit(1)
