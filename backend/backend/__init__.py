# 这将确保在 Django 启动时加载 app，以便 `@shared_task` 能使用它。
from .celery import app as celery_app

__all__ = ('celery_app',)