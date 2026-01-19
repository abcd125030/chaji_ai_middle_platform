"""
Redis缓存管理器
用于优化高并发场景下的任务状态查询
"""
import json
import logging
from typing import Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

class TaskCacheManager:
    """任务缓存管理器"""
    
    # 缓存键前缀
    CACHE_PREFIX = "image_task"
    
    # 缓存过期时间（秒）
    CACHE_TTL = {
        'processing': 300,  # 处理中的任务缓存5分钟
        'success': 3600,    # 成功的任务缓存1小时
        'failed': 1800,     # 失败的任务缓存30分钟
        'batch': 600,       # 批量任务缓存10分钟
    }
    
    # 热点数据缓存时间
    HOT_DATA_TTL = 60  # 1分钟
    
    @classmethod
    def get_cache_key(cls, task_id: str, prefix: str = None) -> str:
        """生成缓存键"""
        if prefix:
            return f"{cls.CACHE_PREFIX}:{prefix}:{task_id}"
        return f"{cls.CACHE_PREFIX}:{task_id}"
    
    @classmethod
    def set_task(cls, task_id: str, task_data: Dict[str, Any], status: str = 'processing') -> bool:
        """设置任务缓存
        
        Args:
            task_id: 任务ID
            task_data: 任务数据字典
            status: 任务状态，用于确定缓存时间
        
        Returns:
            bool: 是否设置成功
        """
        try:
            cache_key = cls.get_cache_key(task_id)
            ttl = cls.CACHE_TTL.get(status, cls.CACHE_TTL['processing'])
            
            # 序列化任务数据
            cache_data = json.dumps(task_data, default=str)
            
            # 设置缓存
            success = cache.set(cache_key, cache_data, ttl)
            
            if success:
                logger.debug(f"任务缓存设置成功 - ID: {task_id}, TTL: {ttl}秒")
                
                # 更新热点数据统计
                cls._update_hot_data_stats(task_id)
            else:
                logger.warning(f"任务缓存设置失败 - ID: {task_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"设置任务缓存异常 - ID: {task_id}, 错误: {str(e)}")
            return False
    
    @classmethod
    def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务缓存
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务数据字典，如果不存在返回None
        """
        try:
            cache_key = cls.get_cache_key(task_id)
            cache_data = cache.get(cache_key)
            
            if cache_data:
                logger.debug(f"任务缓存命中 - ID: {task_id}")
                
                # 更新热点数据统计
                cls._update_hot_data_stats(task_id)
                
                # 反序列化数据
                return json.loads(cache_data)
            else:
                logger.debug(f"任务缓存未命中 - ID: {task_id}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"任务缓存数据格式错误 - ID: {task_id}, 错误: {str(e)}")
            # 删除损坏的缓存
            cls.delete_task(task_id)
            return None
        except Exception as e:
            logger.error(f"获取任务缓存异常 - ID: {task_id}, 错误: {str(e)}")
            return None
    
    @classmethod
    def update_task_status(cls, task_id: str, status: str, additional_data: Dict[str, Any] = None) -> bool:
        """更新任务状态缓存
        
        Args:
            task_id: 任务ID
            status: 新状态
            additional_data: 附加数据
        
        Returns:
            bool: 是否更新成功
        """
        try:
            # 获取现有缓存
            task_data = cls.get_task(task_id)
            
            if task_data:
                # 更新状态
                task_data['status'] = status
                
                # 更新附加数据
                if additional_data:
                    task_data.update(additional_data)
                
                # 重新设置缓存，使用新状态对应的TTL
                return cls.set_task(task_id, task_data, status)
            
            return False
            
        except Exception as e:
            logger.error(f"更新任务状态缓存异常 - ID: {task_id}, 错误: {str(e)}")
            return False
    
    @classmethod
    def delete_task(cls, task_id: str) -> bool:
        """删除任务缓存
        
        Args:
            task_id: 任务ID
        
        Returns:
            bool: 是否删除成功
        """
        try:
            cache_key = cls.get_cache_key(task_id)
            success = cache.delete(cache_key)
            
            if success:
                logger.debug(f"任务缓存删除成功 - ID: {task_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"删除任务缓存异常 - ID: {task_id}, 错误: {str(e)}")
            return False
    
    @classmethod
    def batch_get_tasks(cls, task_ids: list) -> Dict[str, Dict[str, Any]]:
        """批量获取任务缓存
        
        Args:
            task_ids: 任务ID列表
        
        Returns:
            Dict: {task_id: task_data} 的字典
        """
        try:
            # 生成所有缓存键
            cache_keys = {task_id: cls.get_cache_key(task_id) for task_id in task_ids}
            
            # 批量获取缓存
            cache_results = cache.get_many(list(cache_keys.values()))
            
            # 解析结果
            results = {}
            for task_id, cache_key in cache_keys.items():
                cache_data = cache_results.get(cache_key)
                if cache_data:
                    try:
                        results[task_id] = json.loads(cache_data)
                        logger.debug(f"批量缓存命中 - ID: {task_id}")
                    except json.JSONDecodeError:
                        logger.error(f"批量缓存数据格式错误 - ID: {task_id}")
                        cls.delete_task(task_id)
            
            logger.info(f"批量缓存查询 - 请求: {len(task_ids)}, 命中: {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"批量获取任务缓存异常 - 错误: {str(e)}")
            return {}
    
    @classmethod
    def batch_set_tasks(cls, tasks_data: Dict[str, Dict[str, Any]]) -> int:
        """批量设置任务缓存
        
        Args:
            tasks_data: {task_id: task_data} 的字典
        
        Returns:
            int: 成功设置的数量
        """
        try:
            success_count = 0
            cache_data = {}
            
            for task_id, task_data in tasks_data.items():
                cache_key = cls.get_cache_key(task_id)
                status = task_data.get('status', 'processing')
                ttl = cls.CACHE_TTL.get(status, cls.CACHE_TTL['processing'])
                
                # 序列化数据
                cache_data[cache_key] = (json.dumps(task_data, default=str), ttl)
            
            # 批量设置缓存
            for cache_key, (data, ttl) in cache_data.items():
                if cache.set(cache_key, data, ttl):
                    success_count += 1
            
            logger.info(f"批量缓存设置 - 总数: {len(tasks_data)}, 成功: {success_count}")
            return success_count
            
        except Exception as e:
            logger.error(f"批量设置任务缓存异常 - 错误: {str(e)}")
            return 0
    
    @classmethod
    def _update_hot_data_stats(cls, task_id: str):
        """更新热点数据统计（用于监控和优化）"""
        try:
            # 记录访问次数
            stats_key = cls.get_cache_key(task_id, prefix='stats')
            current_count = cache.get(stats_key, 0)
            cache.set(stats_key, current_count + 1, cls.HOT_DATA_TTL)
            
            # 如果访问频繁，可以延长缓存时间
            if current_count > 10:
                logger.info(f"检测到热点数据 - ID: {task_id}, 访问次数: {current_count}")
                
        except Exception as e:
            # 统计失败不影响主流程
            logger.debug(f"更新热点数据统计失败 - ID: {task_id}, 错误: {str(e)}")
    
    @classmethod
    def clear_expired_cache(cls):
        """清理过期缓存（由定时任务调用）"""
        try:
            # Redis会自动处理过期，这里主要用于记录和监控
            logger.info("执行缓存清理检查")
            
        except Exception as e:
            logger.error(f"清理过期缓存异常 - 错误: {str(e)}")

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            # 获取Redis连接信息
            from django.core.cache import caches
            default_cache = caches['default']
            
            if hasattr(default_cache, '_cache'):
                client = default_cache._cache.get_client()
                info = client.info()
                
                return {
                    'used_memory': info.get('used_memory_human', 'N/A'),
                    'connected_clients': info.get('connected_clients', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'hit_rate': round(
                        info.get('keyspace_hits', 0) / 
                        max(info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0), 1) * 100, 
                        2
                    )
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"获取缓存统计信息异常 - 错误: {str(e)}")
            return {}


class UserRateLimiter:
    """用户请求限流器 - 支持按秒限流"""
    
    RATE_LIMIT_PREFIX = "rate_limit"
    
    @classmethod
    def check_rate_limit(cls, user_id: str, limit: int = 100, window: int = 1) -> tuple[bool, int]:
        """检查用户请求是否超过限制
        
        Args:
            user_id: 用户ID
            limit: 时间窗口内的最大请求数
            window: 时间窗口（秒，默认1秒）
        
        Returns:
            (是否允许请求, 当前请求数)
        """
        try:
            # 为按秒限流添加时间戳，支持更精确的滑动窗口
            import time
            current_timestamp = int(time.time())
            
            # 使用时间戳作为key的一部分，实现真正的按秒限流
            if window == 1:
                # 按秒限流时，使用当前秒数作为key
                cache_key = f"{cls.RATE_LIMIT_PREFIX}:{user_id}:{current_timestamp}"
            else:
                # 其他窗口时，使用窗口起始时间
                window_start = (current_timestamp // window) * window
                cache_key = f"{cls.RATE_LIMIT_PREFIX}:{user_id}:{window_start}"
            
            # 获取当前计数
            current_count = cache.get(cache_key, 0)
            
            if current_count >= limit:
                logger.warning(f"用户请求超过限制 - 用户: {user_id}, 当前: {current_count}/{limit} QPS, 窗口: {window}秒")
                return False, current_count
            
            # 增加计数
            # Django的cache接口使用incr方法，如果key不存在会自动创建并设为1
            if current_count == 0:
                # 首次请求，设置初始值1和过期时间
                cache.set(cache_key, 1, window)
                new_count = 1
            else:
                # 使用原子操作增加计数，但不更新过期时间
                try:
                    new_count = cache.incr(cache_key)
                except ValueError:
                    # 如果incr失败（比如key过期了），重新设置
                    cache.set(cache_key, 1, window)
                    new_count = 1
            
            # 记录QPS信息
            if window == 1:
                logger.debug(f"用户QPS检查 - 用户: {user_id}, 当前: {new_count}/{limit} QPS")
            
            return True, new_count
            
        except Exception as e:
            logger.error(f"检查请求限制异常 - 用户: {user_id}, 错误: {str(e)}")
            # 出错时默认允许请求
            return True, 0
    
    @classmethod
    def reset_rate_limit(cls, user_id: str) -> bool:
        """重置用户请求限制
        
        Args:
            user_id: 用户ID
        
        Returns:
            bool: 是否重置成功
        """
        try:
            cache_key = f"{cls.RATE_LIMIT_PREFIX}:{user_id}"
            return cache.delete(cache_key)
            
        except Exception as e:
            logger.error(f"重置请求限制异常 - 用户: {user_id}, 错误: {str(e)}")
            return False