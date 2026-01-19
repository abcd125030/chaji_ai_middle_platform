"""
批量回调管理器
用于在高并发场景下分批延迟发送回调，减少带宽峰值压力
"""
import logging
import time
import json
from typing import Dict, List, Any, Optional
from threading import Lock, Thread
from queue import Queue, Empty
from django.core.cache import cache
# from redis.exceptions import RedisError  # 暂未使用
# import hashlib  # 暂未使用
import random

logger = logging.getLogger(__name__)


class CallbackBatcher:
    """
    批量回调管理器
    - 支持按批次大小和时间窗口触发回调
    - 实现带宽流控，错开高峰
    - 支持失败重试机制
    """
    
    def __init__(self, 
                 batch_size: int = 10,           # 批次大小
                 max_delay: float = 5.0,         # 最大延迟时间（秒）
                 min_interval: float = 0.5,      # 批次间最小间隔（秒）
                 max_bandwidth_mbps: int = 100): # 最大带宽使用（Mbps）
        """
        初始化批量回调管理器
        
        Args:
            batch_size: 每批次最大回调数量
            max_delay: 最大延迟时间，超过此时间强制发送
            min_interval: 批次之间的最小时间间隔
            max_bandwidth_mbps: 最大带宽使用限制
        """
        self.batch_size = batch_size
        self.max_delay = max_delay
        self.min_interval = min_interval
        self.max_bandwidth_mbps = max_bandwidth_mbps
        
        # 回调队列和锁
        self.queue = []
        self.lock = Lock()
        self.last_flush_time = time.time()
        self.last_batch_time = time.time()
        
        # 带宽监控
        self.current_bandwidth_usage = 0
        self.bandwidth_window = []  # 滑动窗口记录带宽使用
        
        # 失败重试队列
        self.retry_queue = Queue()
        
        # 启动后台线程处理定时刷新
        self.running = True
        self.flush_thread = Thread(target=self._auto_flush_worker, daemon=True)
        self.flush_thread.start()
        
        # 启动重试线程
        self.retry_thread = Thread(target=self._retry_worker, daemon=True)
        self.retry_thread.start()
        
        logger.info(f"批量回调管理器初始化 - 批次大小: {batch_size}, "
                   f"最大延迟: {max_delay}秒, 最小间隔: {min_interval}秒")
    
    def add_callback(self, callback_data: Dict[str, Any]) -> bool:
        """
        添加回调到队列
        
        Args:
            callback_data: 回调数据，应包含url和params
        
        Returns:
            bool: 是否添加成功
        """
        try:
            with self.lock:
                # 估算数据大小（base64图片约占原图4/3大小）
                data_size = len(json.dumps(callback_data)) / 1024 / 1024  # MB
                callback_data['_size_mb'] = data_size
                callback_data['_queued_at'] = time.time()
                
                self.queue.append(callback_data)
                
                # 检查是否需要立即刷新
                should_flush = False
                if len(self.queue) >= self.batch_size:
                    logger.info(f"队列达到批次大小 {self.batch_size}，准备刷新")
                    should_flush = True
                elif time.time() - self.last_flush_time > self.max_delay:
                    logger.info(f"超过最大延迟 {self.max_delay}秒，准备刷新")
                    should_flush = True
                
                if should_flush:
                    self._flush_queue()
                
                return True
                
        except Exception as e:
            logger.error(f"添加回调到队列失败 - 错误: {str(e)}")
            return False
    
    def _flush_queue(self):
        """刷新队列，发送批量回调（内部方法，需要在锁内调用）"""
        if not self.queue:
            return
        
        try:
            # 计算批次间隔，实现流控
            time_since_last_batch = time.time() - self.last_batch_time
            if time_since_last_batch < self.min_interval:
                sleep_time = self.min_interval - time_since_last_batch
                logger.debug(f"流控等待 {sleep_time:.2f}秒")
                # 注意：sleep在锁内执行可能影响性能，但确保了顺序性
                # 如果性能有问题，可以考虑在锁外等待
                time.sleep(sleep_time)
            
            # 根据带宽使用情况分批
            batches = self._split_by_bandwidth(self.queue.copy())
            self.queue.clear()
            self.last_flush_time = time.time()
            
            # 错开发送各批次
            for i, batch in enumerate(batches):
                delay = i * self.min_interval  # 每批次递增延迟
                
                # 添加随机抖动，避免批次同时发送
                jitter = random.uniform(0, 0.2)  # 0-200ms随机延迟
                actual_delay = delay + jitter
                
                if delay > 0:
                    logger.info(f"批次 {i+1}/{len(batches)} 将在 {actual_delay:.2f}秒后发送，"
                              f"包含 {len(batch)} 个回调")
                
                # 使用Celery异步发送
                # 延迟导入避免循环引用
                from celery import current_app
                current_app.send_task(
                    'customized.image_editor.tasks.send_batch_callback',
                    args=[batch],
                    countdown=actual_delay  # Celery延迟执行
                )
            
            self.last_batch_time = time.time()
            
            # 更新带宽使用记录
            total_size = sum(cb.get('_size_mb', 0) for batch in batches for cb in batch)
            self._update_bandwidth_usage(total_size)
            
            logger.info(f"已调度 {len(batches)} 个批次，共 {sum(len(b) for b in batches)} 个回调")
            
        except Exception as e:
            logger.error(f"刷新队列失败 - 错误: {str(e)}")
            # 失败的回调放入重试队列
            for callback in self.queue:
                self.retry_queue.put(callback)
    
    def _split_by_bandwidth(self, callbacks: List[Dict]) -> List[List[Dict]]:
        """
        根据带宽限制分割批次
        
        Args:
            callbacks: 待发送的回调列表
        
        Returns:
            分割后的批次列表
        """
        batches = []
        current_batch = []
        current_batch_size = 0
        max_batch_size_mb = self.max_bandwidth_mbps * self.min_interval / 8  # 转换为MB
        
        for callback in callbacks:
            callback_size = callback.get('_size_mb', 0.1)  # 默认0.1MB
            
            # 如果当前批次加上这个回调会超过带宽限制，则创建新批次
            if current_batch and (
                current_batch_size + callback_size > max_batch_size_mb or
                len(current_batch) >= self.batch_size
            ):
                batches.append(current_batch)
                current_batch = []
                current_batch_size = 0
            
            current_batch.append(callback)
            current_batch_size += callback_size
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _update_bandwidth_usage(self, size_mb: float):
        """更新带宽使用记录"""
        current_time = time.time()
        
        # 清理超过1秒的旧记录
        self.bandwidth_window = [
            (t, s) for t, s in self.bandwidth_window 
            if current_time - t < 1.0
        ]
        
        # 添加新记录
        self.bandwidth_window.append((current_time, size_mb))
        
        # 计算当前带宽使用
        self.current_bandwidth_usage = sum(s for _, s in self.bandwidth_window) * 8  # MB/s to Mbps
        
        if self.current_bandwidth_usage > self.max_bandwidth_mbps * 0.8:
            logger.warning(f"带宽使用接近上限 - 当前: {self.current_bandwidth_usage:.1f}Mbps, "
                          f"限制: {self.max_bandwidth_mbps}Mbps")
    
    def _auto_flush_worker(self):
        """后台线程，定期检查并刷新队列"""
        while self.running:
            try:
                time.sleep(1)  # 每秒检查一次
                
                with self.lock:
                    if self.queue and time.time() - self.last_flush_time > self.max_delay:
                        logger.debug(f"自动刷新 - 队列长度: {len(self.queue)}")
                        self._flush_queue()
                        
            except Exception as e:
                logger.error(f"自动刷新线程异常 - 错误: {str(e)}")
    
    def _retry_worker(self):
        """重试线程，处理失败的回调"""
        while self.running:
            try:
                # 从重试队列获取失败的回调
                callback = self.retry_queue.get(timeout=1)
                
                # 增加重试计数
                retry_count = callback.get('_retry_count', 0) + 1
                callback['_retry_count'] = retry_count
                
                if retry_count <= 3:  # 最多重试3次
                    # 指数退避
                    delay = min(60, 2 ** retry_count)
                    logger.info(f"重试回调 - 第 {retry_count} 次，延迟 {delay}秒")
                    
                    time.sleep(delay)
                    self.add_callback(callback)
                else:
                    # 记录失败，可以写入数据库或日志
                    logger.error(f"回调最终失败 - 任务ID: {callback.get('task_id')}, "
                               f"重试次数: {retry_count}")
                    self._record_failed_callback(callback)
                    
            except Empty:
                continue
            except Exception as e:
                logger.error(f"重试线程异常 - 错误: {str(e)}")
    
    def _record_failed_callback(self, callback_data: Dict):
        """记录失败的回调到缓存或数据库"""
        try:
            # 使用Redis记录失败的回调，保留24小时
            failed_key = f"failed_callback:{callback_data.get('task_id', 'unknown')}"
            cache.set(failed_key, json.dumps(callback_data), 86400)
            logger.error(f"已记录失败回调 - Key: {failed_key}")
            
        except Exception as e:
            logger.error(f"记录失败回调出错 - 错误: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批量回调管理器统计信息"""
        with self.lock:
            return {
                'queue_length': len(self.queue),
                'retry_queue_length': self.retry_queue.qsize(),
                'current_bandwidth_mbps': round(self.current_bandwidth_usage, 2),
                'max_bandwidth_mbps': self.max_bandwidth_mbps,
                'last_flush_time': self.last_flush_time,
                'time_since_last_flush': round(time.time() - self.last_flush_time, 2),
                'batch_size': self.batch_size,
                'max_delay': self.max_delay
            }
    
    def force_flush(self):
        """强制刷新队列（用于紧急情况或关闭时）"""
        with self.lock:
            if self.queue:
                logger.info(f"强制刷新队列 - 队列长度: {len(self.queue)}")
                self._flush_queue()
    
    def shutdown(self):
        """关闭批量回调管理器"""
        logger.info("正在关闭批量回调管理器...")
        self.running = False
        
        # 强制刷新剩余的回调
        self.force_flush()
        
        # 等待线程结束
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=5)
        if self.retry_thread.is_alive():
            self.retry_thread.join(timeout=5)
        
        logger.info("批量回调管理器已关闭")


# 全局实例
_batcher_instance = None
_batcher_lock = Lock()


def get_callback_batcher() -> CallbackBatcher:
    """获取全局批量回调管理器实例（单例模式）"""
    global _batcher_instance
    
    if _batcher_instance is None:
        with _batcher_lock:
            if _batcher_instance is None:
                # 从配置读取参数
                from .performance_settings import BATCH_CALLBACK_CONFIG
                _batcher_instance = CallbackBatcher(
                    batch_size=BATCH_CALLBACK_CONFIG.get('BATCH_SIZE', 10),
                    max_delay=BATCH_CALLBACK_CONFIG.get('MAX_DELAY', 5.0),
                    min_interval=BATCH_CALLBACK_CONFIG.get('MIN_INTERVAL', 0.5),
                    max_bandwidth_mbps=BATCH_CALLBACK_CONFIG.get('MAX_BANDWIDTH_MBPS', 100)
                )
    
    return _batcher_instance


def batch_callback_enabled() -> bool:
    """检查是否启用批量回调"""
    from .performance_settings import BATCH_CALLBACK_CONFIG
    return BATCH_CALLBACK_CONFIG.get('ENABLED', False)