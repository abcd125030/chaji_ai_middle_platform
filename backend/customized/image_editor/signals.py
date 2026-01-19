"""
配置更新信号处理
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='image_editor.ImageEditorConfig')
def reload_config_on_save(sender, instance, **kwargs):
    """
    当ImageEditorConfig保存后，通知所有Celery worker重新加载配置
    """
    try:
        # 清除Django进程的缓存（admin进程）
        from .config_manager import ConfigManager
        ConfigManager.clear_cache()
        logger.info(f"配置 '{instance.name}' 已更新，清除Django进程缓存")
        
        # 向所有worker发送配置重载任务
        # 注意：这个任务会被发送到队列，由worker自己处理
        from .tasks import reload_worker_config
        
        # 使用apply_async发送任务，所有监听该队列的worker都会收到并执行
        result = reload_worker_config.apply_async(
            kwargs={'config_name': instance.name},
            queue='celery',  # 使用默认队列
            expires=60,  # 60秒后过期
        )
        
        logger.info(f"已发送配置重载任务到队列: task_id={result.id}, config={instance.name}")
        
    except Exception as e:
        logger.error(f"发送配置重载任务失败: {e}")