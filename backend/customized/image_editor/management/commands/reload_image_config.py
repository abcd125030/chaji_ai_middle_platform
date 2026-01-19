from django.core.management.base import BaseCommand
from django.core.cache import cache
from customized.image_editor.config_manager import config_manager, CACHE_KEY, CACHE_TIMEOUT
from customized.image_editor.config_models import ImageEditorConfig
from customized.image_editor.tasks import reload_worker_config


class Command(BaseCommand):
    help = '清除图片编辑器配置缓存并重新加载'

    def add_arguments(self, parser):
        parser.add_argument(
            '--workers',
            action='store_true',
            help='同时通知所有Celery worker重新加载配置',
        )

    def handle(self, *args, **options):
        self.stdout.write('\n正在清除配置缓存...')
        
        # 清除所有相关缓存
        cache.delete(CACHE_KEY)
        cache.delete('image_editor_config')
        cache.delete('image_editor_active_config')
        
        self.stdout.write(self.style.SUCCESS('✓ 缓存已清除'))
        
        # 重新加载配置
        self.stdout.write('\n正在重新加载配置...')
        config = config_manager.reload()
        
        if config:
            self.stdout.write(self.style.SUCCESS(f'✓ 配置已重新加载: {config.get("name", "unknown")}'))
            
            # 显示当前配置信息
            self.stdout.write('\n当前配置信息:')
            self.stdout.write(f'  - 配置名称: {config.get("name")}')
            self.stdout.write(f'  - 生成模型: {config.get("generation_model")}')
            self.stdout.write(f'  - 检测模型: {config.get("detection_model")}')
            self.stdout.write(f'  - 文生图模型: {config.get("t2i_model")}')
            self.stdout.write(f'  - 背景移除: {"启用" if config.get("enable_bg_removal") else "禁用"}')
            self.stdout.write(f'  - 缓存超时: {CACHE_TIMEOUT} 秒')
            
            # 如果指定了--workers参数，通知所有worker
            if options.get('workers'):
                self.stdout.write('\n正在通知Celery worker重新加载配置...')
                try:
                    result = reload_worker_config.apply_async(
                        kwargs={'config_name': config.get("name")},
                        queue='celery',
                        expires=60,
                    )
                    self.stdout.write(self.style.SUCCESS(f'✓ 已发送重载任务到Celery队列: {result.id}'))
                    self.stdout.write('  Worker将在处理该任务时自动重新加载配置')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ 发送重载任务失败: {e}'))
        else:
            self.stdout.write(self.style.ERROR('✗ 配置加载失败'))
            
        # 检查数据库中的配置
        self.stdout.write('\n数据库配置状态:')
        active_configs = ImageEditorConfig.objects.filter(is_active=True)
        if active_configs.exists():
            for config in active_configs:
                self.stdout.write(f'  - {config.name}: 激活状态')
        else:
            self.stdout.write(self.style.WARNING('  - 没有激活的配置'))
            
        self.stdout.write('\n' + self.style.SUCCESS('配置重新加载完成！'))
        
        if not options.get('workers'):
            self.stdout.write('提示：使用 --workers 参数可以同时通知所有Celery worker重新加载配置')
            self.stdout.write('例如：python manage.py reload_image_config --workers\n')
        else:
            self.stdout.write('✓ 已通知所有Celery worker重新加载配置\n')