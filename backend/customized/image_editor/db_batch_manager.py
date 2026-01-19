"""
数据库批量写入管理器
用于优化数据库写入操作，减少连接池压力
"""
import logging
import threading
import time
from typing import List, Dict, Any, Optional
from django.db import connection
from backend.utils.db_connection import ensure_db_connection_safe
from django.utils import timezone
from collections import defaultdict
from contextlib import contextmanager
import queue

logger = logging.getLogger(__name__)


class BatchWriteManager:
    """批量写入管理器"""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 1.0):
        """
        初始化批量写入管理器
        
        Args:
            batch_size: 批量写入的大小
            flush_interval: 自动刷新间隔（秒）
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.write_queue = queue.Queue()
        self.update_batches = defaultdict(list)
        self.insert_batches = defaultdict(list)
        self.lock = threading.RLock()
        self.running = False
        self.flush_thread = None
        self.stats = {
            'total_writes': 0,
            'batch_flushes': 0,
            'errors': 0,
            'last_flush_time': None
        }
        
    def start(self):
        """启动批量写入管理器"""
        if not self.running:
            self.running = True
            self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
            self.flush_thread.start()
            logger.info("批量写入管理器已启动")
    
    def stop(self):
        """停止批量写入管理器"""
        if self.running:
            self.running = False
            self.flush_all()  # 确保所有数据都被写入
            if self.flush_thread:
                self.flush_thread.join(timeout=5)
            logger.info("批量写入管理器已停止")
    
    def add_update(self, model_class, filter_kwargs: Dict, update_fields: Dict):
        """
        添加更新操作到批量队列
        
        Args:
            model_class: Django模型类
            filter_kwargs: 查询条件
            update_fields: 要更新的字段
        """
        with self.lock:
            key = f"{model_class.__name__}"
            self.update_batches[key].append({
                'model': model_class,
                'filter': filter_kwargs,
                'fields': update_fields,
                'timestamp': time.time()
            })
            
            # 检查是否需要立即刷新
            if len(self.update_batches[key]) >= self.batch_size:
                self._flush_model_updates(key)
    
    def bulk_update_fields(self, model_class, updates: List[Dict[str, Any]], fields: List[str]):
        """
        批量更新特定字段 - 不使用事务以兼容 PgBouncer
        
        Args:
            model_class: Django模型类
            updates: 更新数据列表，每个元素包含id和要更新的字段值
            fields: 要更新的字段列表
        """
        if not updates:
            return
            
        try:
            # 移除 transaction.atomic() 以避免 PgBouncer 连接绑定问题
            # 使用bulk_update进行批量更新
            objects_to_update = []
            for update_data in updates:
                obj_id = update_data.pop('id', None) or update_data.pop('pk', None)
                if obj_id:
                    obj = model_class(pk=obj_id, **update_data)
                    objects_to_update.append(obj)
            
            if objects_to_update:
                model_class.objects.bulk_update(objects_to_update, fields, batch_size=50)
                self.stats['total_writes'] += len(objects_to_update)
                logger.debug(f"批量更新{len(objects_to_update)}条{model_class.__name__}记录")
                    
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"批量更新失败: {str(e)}", exc_info=True)
    
    def _flush_worker(self):
        """后台刷新线程"""
        while self.running:
            time.sleep(self.flush_interval)
            self.flush_all()
    
    def flush_all(self):
        """刷新所有待处理的批量操作"""
        with self.lock:
            # 只有当有数据需要刷新时才检查连接
            if not any(self.update_batches.values()) and not any(self.insert_batches.values()):
                return  # 没有待处理的数据，直接返回
                
            try:
                # 确保连接有效
                ensure_db_connection_safe()
                # 刷新所有更新批次
                for key in list(self.update_batches.keys()):
                    if self.update_batches[key]:
                        self._flush_model_updates(key)
                
                self.stats['last_flush_time'] = timezone.now()
            except Exception as e:
                if 'client_idle_timeout' in str(e) or 'connection already closed' in str(e):
                    logger.warning(f"flush_all 检测到连接超时，重新连接后重试: {str(e)}")
                    ensure_db_connection_safe()
                    # 重试
                    for key in list(self.update_batches.keys()):
                        if self.update_batches[key]:
                            self._flush_model_updates(key)
                    self.stats['last_flush_time'] = timezone.now()
                else:
                    raise
    
    def _flush_model_updates(self, key: str):
        """
        刷新特定模型的更新批次
        
        Args:
            key: 模型键名
        """
        updates = self.update_batches[key]
        if not updates:
            return
            
        try:
            # 按模型分组
            model_updates = defaultdict(list)
            for update in updates:
                model = update['model']
                model_updates[model].append(update)
            
            # 批量执行更新
            for model, batch in model_updates.items():
                self._execute_batch_updates(model, batch)
            
            # 清空批次
            self.update_batches[key] = []
            self.stats['batch_flushes'] += 1
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"刷新批量更新失败: {str(e)}", exc_info=True)
    
    def _execute_batch_updates(self, model_class, updates: List[Dict]):
        """
        执行批量更新 - 不使用事务以兼容 PgBouncer
        
        Args:
            model_class: Django模型类
            updates: 更新列表
        """
        # 合并相同过滤条件的更新
        merged_updates = {}
        for update in updates:
            filter_key = str(update['filter'])
            if filter_key not in merged_updates:
                merged_updates[filter_key] = {
                    'filter': update['filter'],
                    'fields': update['fields']
                }
            else:
                # 合并字段更新
                merged_updates[filter_key]['fields'].update(update['fields'])
        
        # 执行更新 - 不使用事务，直接更新以兼容 PgBouncer
        try:
            # 使用新连接避免长时间空闲
            ensure_db_connection_safe()
            # 移除 transaction.atomic() 以避免 PgBouncer 连接绑定问题
            for update_data in merged_updates.values():
                model_class.objects.filter(**update_data['filter']).update(**update_data['fields'])
                self.stats['total_writes'] += 1
        except Exception as e:
            # 检查是否是连接超时错误
            if 'client_idle_timeout' in str(e) or 'connection already closed' in str(e):
                logger.warning(f"检测到连接超时，尝试重新连接并重试: {str(e)}")
                ensure_db_connection_safe()
                # 重试一次，同样不使用事务
                for update_data in merged_updates.values():
                    model_class.objects.filter(**update_data['filter']).update(**update_data['fields'])
                    self.stats['total_writes'] += 1
            else:
                raise
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return self.stats.copy()


class ConnectionPoolManager:
    """数据库连接池管理器"""
    
    def __init__(self, max_connections: int = 50):
        """
        初始化连接池管理器
        
        Args:
            max_connections: 最大连接数
        """
        self.max_connections = max_connections
        self.active_connections = 0
        self.lock = threading.Lock()
        self.connection_semaphore = threading.Semaphore(max_connections)
        
    @contextmanager
    def get_connection(self, timeout: float = 10.0):
        """
        获取数据库连接上下文管理器
        
        Args:
            timeout: 获取连接的超时时间
            
        Yields:
            数据库连接
        """
        acquired = self.connection_semaphore.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError("无法获取数据库连接")
            
        try:
            with self.lock:
                self.active_connections += 1
                logger.debug(f"活跃连接数: {self.active_connections}/{self.max_connections}")
            
            yield connection
            
        finally:
            with self.lock:
                self.active_connections -= 1
            self.connection_semaphore.release()
    
    def get_status(self) -> Dict:
        """获取连接池状态"""
        with self.lock:
            return {
                'max_connections': self.max_connections,
                'active_connections': self.active_connections,
                'available_connections': self.max_connections - self.active_connections
            }


class TaskDatabaseOptimizer:
    """任务数据库操作优化器"""
    
    def __init__(self):
        # 减小批量大小和刷新间隔，降低延迟
        # batch_size=10: 积累10个就刷新，避免长时间等待
        # flush_interval=0.1: 100ms自动刷新，减少等待时间
        self.batch_manager = BatchWriteManager(batch_size=10, flush_interval=0.1)
        self.connection_pool = ConnectionPoolManager(max_connections=30)
        self._started = False
        
    def _ensure_started(self):
        """确保批量管理器已启动（懒加载）"""
        if not self._started:
            self.batch_manager.start()
            self._started = True
            logger.debug("TaskDatabaseOptimizer 懒加载启动")
    
    def update_task_status(self, task_id: str, status: Optional[str], extra_fields: Optional[Dict] = None):
        """
        优化的任务状态更新
        
        Args:
            task_id: 任务ID
            status: 任务状态（如果为None则不更新状态）
            extra_fields: 额外要更新的字段
        """
        self._ensure_started()  # 确保已启动
        from .models import ImageEditTask
        
        update_fields = {}
        if status is not None:
            update_fields['status'] = status
        if extra_fields:
            update_fields.update(extra_fields)
        
        # 只有在有字段需要更新时才添加到批量队列
        if update_fields:
            # 添加到批量更新队列
            self.batch_manager.add_update(
                ImageEditTask,
                {'task_id': task_id},
                update_fields
            )
    
    def batch_update_tasks(self, task_updates: List[Dict]):
        """
        批量更新任务
        
        Args:
            task_updates: 任务更新列表
        """
        from .models import ImageEditTask
        
        if not task_updates:
            return
            
        # 提取要更新的字段
        fields_set = set()
        for update in task_updates:
            fields_set.update(update.keys())
        fields_set.discard('task_id')  # 移除ID字段
        
        # 准备批量更新数据
        updates_data = []
        for update in task_updates:
            task_id = update.pop('task_id', None)
            if task_id:
                update['id'] = task_id
                updates_data.append(update)
        
        # 执行批量更新
        self.batch_manager.bulk_update_fields(
            ImageEditTask,
            updates_data,
            list(fields_set)
        )
    
    def flush(self):
        """立即刷新所有待处理的操作"""
        self._ensure_started()  # 确保已启动
        self.batch_manager.flush_all()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        # get_stats 不需要启动，如果未启动则返回默认值
        if not self._started:
            return {
                'batch_stats': {'status': 'not_started'},
                'connection_pool': {'status': 'not_started'}
            }
        return {
            'batch_stats': self.batch_manager.get_stats(),
            'connection_pool': self.connection_pool.get_status()
        }
    
    def shutdown(self):
        """关闭优化器"""
        if self._started:
            self.batch_manager.stop()
            self._started = False


# 全局实例
db_optimizer = TaskDatabaseOptimizer()