"""
基于Redis的全局批量回调管理器
解决多worker并发问题，实现真正的全局流控
"""
import logging
import time
import json
import random
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class RedisCallbackBatcher:
    """
    基于Redis的全局批量回调管理器
    - 使用Redis作为全局队列，所有worker共享
    - 单一调度器模式，避免并发冲突
    - 实现真正的带宽流控
    """
    
    QUEUE_KEY = "callback_queue:pending"
    PROCESSING_KEY = "callback_queue:processing"
    LOCK_KEY = "callback_queue:lock"
    LAST_SEND_KEY = "callback_queue:last_send_time"
    STATS_KEY = "callback_queue:stats"
    
    def __init__(self):
        """初始化Redis连接"""
        # 获取Redis连接
        try:
            # 方法1: 尝试从django-redis获取原生客户端
            from django_redis import get_redis_connection
            self.redis_client = get_redis_connection("default")
        except ImportError:
            # 方法2: 如果没有django-redis，直接创建连接
            import redis
            from django.conf import settings
            cache_location = settings.CACHES['default'].get('LOCATION', 'redis://localhost:6379/1')
            self.redis_client = redis.from_url(cache_location)
        
        # 从配置读取参数
        from .performance_settings import BATCH_CALLBACK_CONFIG
        self.config = BATCH_CALLBACK_CONFIG
        self.batch_size = self.config.get('BATCH_SIZE', 10)
        self.max_delay = self.config.get('MAX_DELAY', 5.0)
        self.min_interval = self.config.get('MIN_INTERVAL', 0.5)
        
    def add_callback(self, callback_data: Dict[str, Any]) -> bool:
        """
        添加回调到Redis队列
        
        Args:
            callback_data: 回调数据
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 添加时间戳
            callback_data['_queued_at'] = time.time()
            
            # 序列化并加入队列
            serialized = json.dumps(callback_data, default=str)
            self.redis_client.rpush(self.QUEUE_KEY, serialized)
            
            # 更新统计
            self._update_stats('queued')
            
            # 检查是否需要触发发送
            queue_length = self.redis_client.llen(self.QUEUE_KEY)
            logger.debug(f"当前队列长度: {queue_length}, 批次大小: {self.batch_size}")
            
            if queue_length >= self.batch_size:
                logger.info(f"队列达到批次大小 {self.batch_size}，触发发送")
                # 使用Celery发送任务，指定队列
                from celery import current_app
                result = current_app.send_task('customized.image_editor.tasks_batch.trigger_batch_send', 
                                    queue='celery')
                logger.info(f"触发任务已发送，任务ID: {result.id}")
            elif self._should_flush_by_time():
                logger.info(f"超过最大延迟时间，触发发送")
                from celery import current_app
                result = current_app.send_task('customized.image_editor.tasks_batch.trigger_batch_send',
                                    queue='celery')
                logger.info(f"触发任务已发送，任务ID: {result.id}")
            else:
                logger.debug(f"暂不触发发送，等待更多回调或超时")
            
            return True
            
        except Exception as e:
            logger.error(f"添加回调到Redis队列失败 - 错误: {str(e)}")
            return False
    
    def get_batch(self) -> List[Dict]:
        """
        从队列获取一批回调（原子操作）
        
        Returns:
            回调数据列表
        """
        batch = []
        
        try:
            # 使用Lua脚本实现原子操作
            lua_script = """
            local batch_size = tonumber(ARGV[1])
            local queue_key = KEYS[1]
            local processing_key = KEYS[2]
            
            local batch = {}
            for i=1,batch_size do
                local item = redis.call('lpop', queue_key)
                if item then
                    table.insert(batch, item)
                    redis.call('rpush', processing_key, item)
                else
                    break
                end
            end
            
            return batch
            """
            
            # 执行Lua脚本
            # Redis eval的参数顺序: script, numkeys, *keys, *args
            batch_data = self.redis_client.eval(
                lua_script,
                2,  # number of keys
                self.QUEUE_KEY,
                self.PROCESSING_KEY,
                self.batch_size
            )
            
            # 确保batch_data是列表
            if batch_data is None:
                batch_data = []
            
            # 反序列化
            for item in batch_data:
                try:
                    batch.append(json.loads(item))
                except json.JSONDecodeError:
                    logger.error(f"反序列化失败: {item}")
            
            if batch:
                logger.info(f"从队列获取 {len(batch)} 个回调")
                
        except Exception as e:
            logger.error(f"获取批次失败 - 错误: {str(e)}")
        
        return batch
    
    def _should_flush_by_time(self) -> bool:
        """检查是否应该基于时间触发发送"""
        try:
            # 获取队列中最早的元素时间
            first_item = self.redis_client.lindex(self.QUEUE_KEY, 0)
            if not first_item:
                logger.debug("队列为空，无需时间触发")
                return False
            
            data = json.loads(first_item)
            queued_at = data.get('_queued_at', time.time())
            time_elapsed = time.time() - queued_at
            
            logger.debug(f"最早任务等待时间: {time_elapsed:.2f}秒, 最大延迟: {self.max_delay}秒")
            
            # 检查是否超过最大延迟
            return time_elapsed > self.max_delay
            
        except Exception as e:
            logger.error(f"检查时间触发失败 - 错误: {str(e)}")
            return False
    
    def acquire_send_lock(self, timeout: int = 30) -> bool:
        """
        获取发送锁（避免多个worker同时发送）
        
        Args:
            timeout: 锁超时时间
            
        Returns:
            bool: 是否获取成功
        """
        try:
            # 使用Redis的SET NX实现分布式锁
            lock_value = f"worker_{time.time()}_{random.randint(1000, 9999)}"
            acquired = self.redis_client.set(
                self.LOCK_KEY,
                lock_value,
                nx=True,  # 仅在不存在时设置
                ex=timeout  # 超时时间
            )
            
            if acquired:
                logger.debug(f"获取发送锁成功: {lock_value}")
                return True
            else:
                logger.debug("发送锁已被其他worker持有")
                return False
                
        except Exception as e:
            logger.error(f"获取发送锁失败 - 错误: {str(e)}")
            return False
    
    def release_send_lock(self):
        """释放发送锁"""
        try:
            self.redis_client.delete(self.LOCK_KEY)
            logger.debug("释放发送锁")
        except Exception as e:
            logger.error(f"释放发送锁失败 - 错误: {str(e)}")
    
    def check_send_interval(self) -> float:
        """
        检查距离上次发送的时间间隔
        
        Returns:
            需要等待的时间（秒）
        """
        try:
            last_send = self.redis_client.get(self.LAST_SEND_KEY)
            if last_send:
                last_send_time = float(last_send)
                time_since_last = time.time() - last_send_time
                
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    return wait_time
            
            return 0
            
        except Exception as e:
            logger.error(f"检查发送间隔失败 - 错误: {str(e)}")
            return 0
    
    def update_last_send_time(self):
        """更新最后发送时间"""
        try:
            self.redis_client.set(
                self.LAST_SEND_KEY,
                str(time.time()),
                ex=60  # 60秒过期
            )
        except Exception as e:
            logger.error(f"更新发送时间失败 - 错误: {str(e)}")
    
    def _update_stats(self, action: str):
        """更新统计信息"""
        try:
            stats_key = f"{self.STATS_KEY}:{action}"
            self.redis_client.incr(stats_key)
            
            # 设置过期时间为1天
            self.redis_client.expire(stats_key, 86400)
            
        except Exception as e:
            logger.error(f"更新统计失败 - 错误: {str(e)}")
    
    def get_queue_stats(self) -> Dict:
        """获取队列统计信息"""
        try:
            pending = self.redis_client.llen(self.QUEUE_KEY)
            processing = self.redis_client.llen(self.PROCESSING_KEY)
            
            # 获取统计数据（Redis返回的是bytes，需要decode）
            queued = self.redis_client.get(f"{self.STATS_KEY}:queued")
            sent = self.redis_client.get(f"{self.STATS_KEY}:sent")
            failed = self.redis_client.get(f"{self.STATS_KEY}:failed")
            
            # 处理None和bytes类型
            queued = int(queued.decode() if queued else 0)
            sent = int(sent.decode() if sent else 0)
            failed = int(failed.decode() if failed else 0)
            
            return {
                'pending': pending,
                'processing': processing,
                'total_queued': queued,
                'total_sent': sent,
                'total_failed': failed,
                'config': {
                    'batch_size': self.batch_size,
                    'max_delay': self.max_delay,
                    'min_interval': self.min_interval
                }
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败 - 错误: {str(e)}")
            return {}
    
    def clear_processing_queue(self):
        """清理处理中队列（用于错误恢复）"""
        try:
            # 将处理中的任务移回待处理队列
            while True:
                item = self.redis_client.lpop(self.PROCESSING_KEY)
                if not item:
                    break
                self.redis_client.rpush(self.QUEUE_KEY, item)
            
            logger.info("已清理处理中队列")
            
        except Exception as e:
            logger.error(f"清理处理中队列失败 - 错误: {str(e)}")


# 全局实例
_redis_batcher = None


def get_redis_batcher() -> RedisCallbackBatcher:
    """获取Redis批量回调管理器实例"""
    global _redis_batcher
    if _redis_batcher is None:
        _redis_batcher = RedisCallbackBatcher()
    return _redis_batcher