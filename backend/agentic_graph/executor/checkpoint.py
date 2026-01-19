"""
检查点管理器
"""
import json
import logging
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger('django')


class CheckpointManager:
    """检查点管理器，负责保存和恢复执行状态"""
    
    def __init__(self, use_cache: bool = True, cache_timeout: int = 3600):
        """
        初始化检查点管理器
        
        参数:
            use_cache: 是否使用缓存
            cache_timeout: 缓存超时时间（秒）
        """
        self.use_cache = use_cache
        self.cache_timeout = cache_timeout
    
    def save(self, task_id: str, state_data: Dict[str, Any]) -> bool:
        """
        保存检查点
        
        参数:
            task_id: 任务ID
            state_data: 状态数据
        
        返回:
            是否保存成功
        """
        try:
            # 保存到缓存
            if self.use_cache:
                cache_key = self._get_cache_key(task_id)
                cache.set(cache_key, state_data, timeout=self.cache_timeout)
            
            # 保存到数据库
            from ..models import GraphCheckpoint
            
            with transaction.atomic():
                checkpoint, created = GraphCheckpoint.objects.update_or_create(
                    task_id=task_id,
                    defaults={
                        'state_data': state_data,
                        'checkpoint_count': state_data.get('checkpoint_count', 0)
                    }
                )
            
            logger.info(f"保存检查点成功 - task_id: {task_id}, checkpoint_count: {state_data.get('checkpoint_count', 0)}")
            return True
            
        except Exception as e:
            logger.error(f"保存检查点失败 - task_id: {task_id}, 错误: {e}", exc_info=True)
            return False
    
    def load(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        加载检查点
        
        参数:
            task_id: 任务ID
        
        返回:
            状态数据，如果不存在返回 None
        """
        try:
            # 先从缓存加载
            if self.use_cache:
                cache_key = self._get_cache_key(task_id)
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.info(f"从缓存加载检查点 - task_id: {task_id}")
                    return cached_data
            
            # 从数据库加载
            from ..models import GraphCheckpoint
            
            try:
                checkpoint = GraphCheckpoint.objects.get(task_id=task_id)
                state_data = checkpoint.state_data
                
                # 更新缓存
                if self.use_cache and state_data:
                    cache_key = self._get_cache_key(task_id)
                    cache.set(cache_key, state_data, timeout=self.cache_timeout)
                
                logger.info(f"从数据库加载检查点 - task_id: {task_id}")
                return state_data
                
            except GraphCheckpoint.DoesNotExist:
                logger.info(f"检查点不存在 - task_id: {task_id}")
                return None
                
        except Exception as e:
            logger.error(f"加载检查点失败 - task_id: {task_id}, 错误: {e}", exc_info=True)
            return None
    
    def delete(self, task_id: str) -> bool:
        """
        删除检查点
        
        参数:
            task_id: 任务ID
        
        返回:
            是否删除成功
        """
        try:
            # 删除缓存
            if self.use_cache:
                cache_key = self._get_cache_key(task_id)
                cache.delete(cache_key)
            
            # 删除数据库记录
            from ..models import GraphCheckpoint
            
            GraphCheckpoint.objects.filter(task_id=task_id).delete()
            
            logger.info(f"删除检查点成功 - task_id: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除检查点失败 - task_id: {task_id}, 错误: {e}", exc_info=True)
            return False
    
    def _get_cache_key(self, task_id: str) -> str:
        """获取缓存键"""
        return f"graph_checkpoint:{task_id}"