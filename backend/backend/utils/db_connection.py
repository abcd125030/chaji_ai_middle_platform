"""
数据库连接恢复工具
专门处理 gevent + PgBouncer 环境下的连接问题
"""

import logging
from django.db import connection, connections, close_old_connections
from django.db.utils import OperationalError
import time

logger = logging.getLogger('django')


def ensure_db_connection_safe():
    """
    安全地确保数据库连接可用
    
    这个函数处理 gevent + PgBouncer 环境下的连接问题：
    1. 首先尝试关闭旧连接
    2. 然后测试连接是否可用
    3. 如果连接不可用，强制关闭并重建
    """
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            # 首先尝试检查连接是否可用
            if attempt == 0:
                # 第一次尝试，先用 is_usable() 快速检查
                try:
                    if not connection.is_usable():
                        # 降低日志级别为 debug，减少干扰
                        logger.debug(f"连接不可用，尝试重建 (尝试 {attempt + 1}/{max_attempts})")
                        connection.close()
                except Exception as e:
                    # is_usable() 本身也可能失败
                    logger.debug(f"检查连接状态失败: {e}，强制关闭")
                    try:
                        connection.close()
                    except:
                        pass  # 忽略关闭错误
            elif attempt == 1:
                # 第二次尝试，使用 close_old_connections
                logger.warning(f"使用 close_old_connections (尝试 {attempt + 1}/{max_attempts})")
                close_old_connections()
            else:
                # 第三次尝试，强制关闭所有连接
                logger.warning(f"强制关闭连接 (尝试 {attempt + 1}/{max_attempts})")
                try:
                    connection.close()
                    # 对于默认连接，也尝试从 connections 字典中关闭
                    if 'default' in connections:
                        connections['default'].close()
                except:
                    pass  # 忽略关闭错误
                
                # 短暂等待
                time.sleep(0.1)
            
            # 测试连接
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if attempt > 0:
                    logger.info(f"数据库连接恢复成功 (尝试 {attempt + 1}/{max_attempts})")
                return True
                
        except (OperationalError, Exception) as e:
            error_msg = str(e).lower()
            if "the connection is closed" in error_msg or "connection already closed" in error_msg:
                if attempt < max_attempts - 1:
                    logger.warning(f"连接测试失败，将重试: {e}")
                    continue
                else:
                    logger.error(f"所有恢复尝试都失败: {e}")
                    raise
            else:
                # 非连接关闭错误，直接抛出
                logger.error(f"数据库操作失败（非连接问题）: {e}")
                raise
    
    return False


def with_db_retry(func):
    """
    装饰器：自动重试数据库操作
    """
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    ensure_db_connection_safe()
                return func(*args, **kwargs)
            except OperationalError as e:
                if "connection" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"数据库操作失败，尝试重试 ({attempt + 1}/{max_retries}): {e}")
                    continue
                raise
        return None
    
    return wrapper