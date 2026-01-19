from django.apps import AppConfig


class MarketConfig(AppConfig):
    """frago Cloud Market 应用配置"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webapps.market'
    verbose_name = 'Recipe 市场'

    def ready(self):
        """应用就绪时的初始化"""
        pass
