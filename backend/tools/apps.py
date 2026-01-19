from django.apps import AppConfig


class ToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tools'

    def ready(self):
        # 自动发现并加载所有工具
        import importlib
        import pkgutil
        from .core.registry import ToolRegistry
        
        registry = ToolRegistry()
        
        # 遍历 basic 和 advanced 目录
        for sub_dir in ['basic', 'advanced']:
            module_path = f'{self.name}.{sub_dir}' # 使用 self.name 获取应用名称
            try:
                package = importlib.import_module(module_path)
                for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
                    if not modname.startswith('_'):
                        try:
                            importlib.import_module(f'.{modname}', package.__name__)
                        except Exception as e:
                            print(f"Warning: Failed to load tool module {package.__name__}.{modname}: {e}")
            except ImportError:
                pass
