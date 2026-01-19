from django.apps import AppConfig


class ImageEditorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customized.image_editor'
    
    def ready(self):
        """应用准备就绪时导入信号处理器"""
        import customized.image_editor.signals