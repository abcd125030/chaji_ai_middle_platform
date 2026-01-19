"""
PDF Extractor 专用 Celery 应用配置
独立的 Celery 实例，使用独立的 Redis DB (DB 3)
"""
import os
from celery import Celery
from urllib.parse import quote
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 设置 Django 配置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 从环境变量读取 Redis 配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_PASSWORD_QUOTED = quote(REDIS_PASSWORD) if REDIS_PASSWORD else None

# PDF Extractor 使用独立的 Redis DB 3
PDF_EXTRACTOR_CELERY_DB = os.getenv("PDF_EXTRACTOR_CELERY_DB", "3")
PDF_EXTRACTOR_RESULT_DB = os.getenv("PDF_EXTRACTOR_RESULT_DB", "4")

# 构建 broker 和 result backend URL
broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{PDF_EXTRACTOR_CELERY_DB}"
result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{PDF_EXTRACTOR_RESULT_DB}"

if REDIS_PASSWORD:
    broker_url = f"redis://:{REDIS_PASSWORD_QUOTED}@{REDIS_HOST}:{REDIS_PORT}/{PDF_EXTRACTOR_CELERY_DB}"
    result_backend = f"redis://:{REDIS_PASSWORD_QUOTED}@{REDIS_HOST}:{REDIS_PORT}/{PDF_EXTRACTOR_RESULT_DB}"

# 创建独立的 Celery 应用
app = Celery('pdf_extractor')

# 手动配置 Celery（不使用 Django settings 的配置）
app.conf.update(
    broker_url=broker_url,
    result_backend=result_backend,
    broker_transport_options={"visibility_timeout": 3600},
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
    timezone='Asia/Shanghai',

    # Worker 优化配置
    worker_max_tasks_per_child=1000,
    broker_pool_limit=None,
    result_backend_pool_limit=None,
    worker_prefetch_multiplier=4,

    # 结果过期配置
    result_expires=86400,  # 24小时

    # 任务可靠性配置
    task_acks_late=True,  # 任务完成后才确认，防止worker崩溃时任务丢失
    task_reject_on_worker_lost=True,  # worker丢失时拒绝任务，重新入队

    # 只包含 PDF Extractor 相关的任务
    include=['webapps.toolkit.tasks'],

    # 队列配置
    task_default_queue='pdf_extractor',
    task_default_exchange='pdf_extractor',
    task_default_routing_key='pdf_extractor',
)

# 设置 Django
import django
django.setup()

# 自动发现任务（仅限 toolkit 应用）
app.autodiscover_tasks(['webapps.toolkit'])


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    print(f'Broker: {app.conf.broker_url}')
    print(f'Result Backend: {app.conf.result_backend}')
