"""
Xiaohongshu sentiment monitoring application config
"""
from django.apps import AppConfig


class XiaohongshuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webapps.xiaohongshu'
    verbose_name = '小红书舆情监控'
