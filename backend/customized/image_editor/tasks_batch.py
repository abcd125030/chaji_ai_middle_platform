"""
批量回调相关的Celery任务
独立文件避免循环导入
"""
from celery import shared_task
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0, ignore_result=True)
def trigger_batch_send(self):
    """
    触发批量发送任务（Celery任务）
    使用分布式锁确保只有一个worker在发送
    """
    from .callback_batcher_redis import get_redis_batcher
    
    batcher = get_redis_batcher()
    
    # 尝试获取发送锁
    if not batcher.acquire_send_lock():
        logger.debug("其他worker正在发送，跳过本次触发")
        return
    
    try:
        # 检查发送间隔
        wait_time = batcher.check_send_interval()
        if wait_time > 0:
            logger.info(f"距离上次发送间隔太短，等待 {wait_time:.2f}秒")
            time.sleep(wait_time)
        
        # 获取一批回调
        batch = batcher.get_batch()
        if batch:
            # 只有在有数据时才处理
            # 更新最后发送时间
            batcher.update_last_send_time()
            
            # 分散发送，每个回调间隔一定时间
            logger.info(f"开始发送批量回调，数量: {len(batch)}")
            
            # 计算每个回调的延迟
            send_interval = 0.2  # 每个回调间隔200ms
            
            for idx, callback_data in enumerate(batch):
                delay = idx * send_interval
                
                # 为每个回调创建独立的发送任务
                send_single_callback.apply_async(
                    args=[callback_data],
                    countdown=delay,
                    queue='celery'
                )
            
            logger.info(f"已调度 {len(batch)} 个回调，总耗时约 {len(batch) * send_interval:.1f}秒")
            
            # 检查是否还有待发送的回调
            remaining = batcher.redis_client.llen(batcher.QUEUE_KEY)
            if remaining > 0:
                # 延迟触发下一批
                next_trigger_delay = len(batch) * send_interval + batcher.min_interval
                logger.info(f"队列还有 {remaining} 个回调，{next_trigger_delay:.1f}秒后触发下一批")
                trigger_batch_send.apply_async(countdown=next_trigger_delay, queue='celery')
        else:
            logger.debug("队列为空，无需发送")
        
    finally:
        # 释放锁
        batcher.release_send_lock()


@shared_task(bind=True, max_retries=2, ignore_result=True)
def send_single_callback(self, callback_data: Dict):
    """
    发送单个回调（Celery任务）
    """
    from .aiCallback import AICallback
    from .callback_batcher_redis import get_redis_batcher
    import json
    
    batcher = get_redis_batcher()
    serialized_callback = json.dumps(callback_data, default=str)
    
    try:
        task_id = callback_data.get('task_id')
        status = callback_data.get('status')
        url = callback_data.get('url')
        data = callback_data.get('data')
        prompt = callback_data.get('prompt', '')
        
        logger.debug(f"发送单个回调 - 任务ID: {task_id}")
        
        # 使用回调URL初始化AICallback，这样会自动推断环境并使用正确的密钥
        ai_callback = AICallback(callback_url=url)
        
        # 根据状态构造回调数据
        if status == 'success':
            callback_payload = ai_callback.create_success_callback_data(data, prompt=prompt)
        elif status == 'failed':
            callback_payload = ai_callback.create_failed_callback_data(data, prompt=prompt)
        else:
            logger.warning(f"未知的任务状态 - 任务ID: {task_id}, 状态: {status}")
            # 从processing队列移除
            batcher.redis_client.lrem(batcher.PROCESSING_KEY, 1, serialized_callback)
            return
        
        # 发送回调，不需要再传递callback_url
        response = ai_callback.send_callback(callback_payload)
        
        if response and response.status_code == 200:
            logger.info(f"回调发送成功 - 任务ID: {task_id}")
            # 成功后从processing队列移除
            batcher.redis_client.lrem(batcher.PROCESSING_KEY, 1, serialized_callback)
            batcher._update_stats('sent')
        else:
            logger.warning(f"回调发送失败 - 任务ID: {task_id}, 响应: {response.status_code if response else 'None'}")
            raise Exception(f"回调失败: {response.status_code if response else 'No response'}")
        
    except Exception as e:
        logger.error(f"发送回调异常 - 任务ID: {callback_data.get('task_id')}, 错误: {str(e)}")
        
        batcher._update_stats('failed')
        
        # 重试
        if self.request.retries < self.max_retries:
            countdown = 30 * (self.request.retries + 1)
            raise self.retry(exc=e, countdown=countdown)
        else:
            # 达到最大重试次数，从processing队列移除，避免永久占用
            logger.error(f"回调最终失败，移除任务 - 任务ID: {callback_data.get('task_id')}")
            batcher.redis_client.lrem(batcher.PROCESSING_KEY, 1, serialized_callback)


@shared_task(ignore_result=True)
def check_and_flush_callbacks():
    """
    定期检查并发送队列中的回调
    应该通过Celery Beat每隔几秒运行一次
    
    建议配置：
    'check-and-flush-callbacks': {
        'task': 'customized.image_editor.tasks_batch.check_and_flush_callbacks',
        'schedule': 3.0,  # 每3秒检查一次
        'options': {'queue': 'celery'}
    }
    """
    from .callback_batcher_redis import get_redis_batcher
    import json
    
    batcher = get_redis_batcher()
    
    try:
        # 检查队列长度
        queue_length = batcher.redis_client.llen(batcher.QUEUE_KEY)
        
        if queue_length == 0:
            return {'status': 'empty', 'message': '队列为空'}
        
        # 获取最早的任务
        first_item = batcher.redis_client.lindex(batcher.QUEUE_KEY, 0)
        if first_item:
            data = json.loads(first_item)
            queued_at = data.get('_queued_at', time.time())
            time_elapsed = time.time() - queued_at
            
            logger.info(f"回调队列检查 - 待处理: {queue_length}, 最早任务等待: {time_elapsed:.1f}秒")
            
            # 判断是否需要触发发送
            should_send = False
            reason = ""
            
            # 条件1：达到批次大小
            if queue_length >= batcher.batch_size:
                should_send = True
                reason = f"达到批次大小({batcher.batch_size})"
            
            # 条件2：超过最大延迟时间
            elif time_elapsed > batcher.max_delay:
                should_send = True
                reason = f"超过最大延迟({batcher.max_delay}秒)"
            
            # 条件3：虽然没达到批次大小，但已有一定数量且等待了一段时间
            elif queue_length >= 3 and time_elapsed > 2.0:  # 3个任务且等待超过2秒
                should_send = True
                reason = "中等批量触发(3+任务,2+秒)"
            
            if should_send:
                logger.info(f"触发批量发送 - 原因: {reason}")
                trigger_batch_send.apply_async(queue='celery')
                return {
                    'status': 'triggered',
                    'reason': reason,
                    'queue_length': queue_length,
                    'wait_time': time_elapsed
                }
            else:
                return {
                    'status': 'waiting',
                    'queue_length': queue_length,
                    'wait_time': time_elapsed,
                    'batch_size': batcher.batch_size,
                    'max_delay': batcher.max_delay
                }
        
    except Exception as e:
        logger.error(f"检查回调队列失败: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task(ignore_result=True)
def cleanup_stuck_callbacks():
    """
    定期清理卡住的回调任务
    可以通过Celery Beat每5分钟运行一次
    """
    from .callback_batcher_redis import get_redis_batcher
    import json
    import time
    
    batcher = get_redis_batcher()
    
    try:
        # 检查processing队列中的任务
        processing_items = batcher.redis_client.lrange(batcher.PROCESSING_KEY, 0, -1)
        
        stuck_count = 0
        current_time = time.time()
        
        for item in processing_items:
            try:
                data = json.loads(item)
                queued_at = data.get('_queued_at', 0)
                
                # 如果任务在processing队列超过5分钟，认为是卡住了
                if current_time - queued_at > 300:  # 5分钟
                    # 从processing队列移除
                    batcher.redis_client.lrem(batcher.PROCESSING_KEY, 1, item)
                    # 重新加入pending队列
                    batcher.redis_client.rpush(batcher.QUEUE_KEY, item)
                    stuck_count += 1
                    logger.warning(f"恢复卡住的回调 - 任务ID: {data.get('task_id')}")
                    
            except Exception as e:
                logger.error(f"处理卡住任务时出错: {str(e)}")
        
        if stuck_count > 0:
            logger.info(f"清理完成，恢复了 {stuck_count} 个卡住的回调")
            # 触发批量发送
            trigger_batch_send.apply_async(queue='celery')
        
        return stuck_count
        
    except Exception as e:
        logger.error(f"清理卡住回调失败: {str(e)}")
        return 0