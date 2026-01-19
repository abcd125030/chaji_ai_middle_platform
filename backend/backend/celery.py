import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, celeryd_init, task_prerun
import logging

logger = logging.getLogger(__name__)

# 为 'celery' 程序设置默认的 Django 设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

app = Celery('backend')

# 使用字符串意味着 worker 无需将配置对象序列化给子进程。
# namespace='CELERY' 表示所有 celery 相关的配置键都应有 `CELERY_` 前缀。
app.config_from_object('django.conf:settings', namespace='CELERY')

# 从所有已注册的 Django app 加载任务模块。
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

@celeryd_init.connect
def configure_workers(sender=None, conf=None, **kwargs):
    """在worker进程初始化时加载配置"""
    try:
        # 确保Django已经完全初始化
        import django
        django.setup()
        
        # 加载图片编辑器配置
        from customized.image_editor.config_manager import config_manager
        config_manager.reload()
        logger.info("Celery worker配置加载成功")
    except Exception as e:
        logger.error(f"Celery worker配置加载失败: {e}")

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Worker准备就绪时的处理"""
    logger.info(f"Celery worker {sender} 已准备就绪")

@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Worker关闭时的处理"""
    logger.info(f"Celery worker {sender} 正在关闭")