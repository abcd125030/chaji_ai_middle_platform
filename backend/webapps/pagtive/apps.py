from django.apps import AppConfig


class PagtiveConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webapps.pagtive'
    label = 'pagtive'  # 保持与数据库中的记录一致
    verbose_name = 'Pagtive应用'
