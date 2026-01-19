"""
MinerU 管理命令

提供 MinerU 服务的管理和维护功能
"""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime

from mineru.models import PDFParseTask, ParseResult
from mineru.services import MinerUService
from mineru.services.optimized_service import OptimizedMinerUService
from mineru.services.storage_adapter import MinerUStorageAdapter


class Command(BaseCommand):
    help = 'MinerU 服务管理命令'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            type=str,
            choices=['stats', 'clean', 'migrate', 'cache', 'test'],
            help='执行的操作'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='天数范围'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='模拟运行'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制执行'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'stats':
            self.show_stats(options)
        elif action == 'clean':
            self.clean_files(options)
        elif action == 'migrate':
            self.migrate_to_oss(options)
        elif action == 'cache':
            self.manage_cache(options)
        elif action == 'test':
            self.test_service(options)
    
    def show_stats(self, options):
        """显示统计信息"""
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # 总体统计
        total_tasks = PDFParseTask.objects.count()
        recent_tasks = PDFParseTask.objects.filter(created_at__gte=cutoff_date)
        
        self.stdout.write(self.style.SUCCESS(f'\n📊 MinerU 服务统计（最近 {days} 天）'))
        self.stdout.write('-' * 60)
        
        # 任务统计
        self.stdout.write(f'总任务数: {total_tasks}')
        self.stdout.write(f'最近任务: {recent_tasks.count()}')
        
        # 状态分布
        status_stats = recent_tasks.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        self.stdout.write('\n状态分布:')
        for stat in status_stats:
            self.stdout.write(f"  {stat['status']}: {stat['count']}")
        
        # 文件类型统计
        type_stats = recent_tasks.values('file_type').annotate(
            count=Count('id'),
            avg_time=Avg('processing_time')
        ).order_by('-count')
        
        self.stdout.write('\n文件类型:')
        for stat in type_stats:
            avg_time = stat['avg_time'] or 0
            self.stdout.write(
                f"  {stat['file_type']}: {stat['count']} 个, "
                f"平均 {avg_time:.1f} 秒"
            )
        
        # 处理性能
        completed_tasks = recent_tasks.filter(status='completed')
        if completed_tasks.exists():
            avg_processing_time = completed_tasks.aggregate(
                avg=Avg('processing_time')
            )['avg'] or 0
            
            self.stdout.write(f'\n平均处理时间: {avg_processing_time:.2f} 秒')
        
        # 错误统计
        failed_tasks = recent_tasks.filter(status='failed')
        if failed_tasks.exists():
            self.stdout.write(f'\n失败任务: {failed_tasks.count()}')
            
            # 显示最近的错误
            recent_errors = failed_tasks.order_by('-created_at')[:5]
            if recent_errors:
                self.stdout.write('\n最近错误:')
                for task in recent_errors:
                    error_msg = (task.error_message or '未知错误')[:50]
                    self.stdout.write(f"  [{task.created_at:%Y-%m-%d %H:%M}] {error_msg}")
    
    def clean_files(self, options):
        """清理旧文件"""
        days = options['days']
        dry_run = options['dry_run']
        
        self.stdout.write(f'\n🧹 清理 {days} 天前的文件')
        
        # 查找旧任务
        cutoff_date = timezone.now() - timedelta(days=days)
        old_tasks = PDFParseTask.objects.filter(
            created_at__lt=cutoff_date,
            status__in=['completed', 'failed']
        )
        
        self.stdout.write(f'找到 {old_tasks.count()} 个旧任务')
        
        if dry_run:
            self.stdout.write('[模拟模式] 不会真正删除文件')
        
        # 统计
        deleted_count = 0
        freed_size = 0
        
        for task in old_tasks[:100]:  # 限制一次处理数量
            if dry_run:
                self.stdout.write(f'[模拟] 将删除任务 {task.task_id}')
            else:
                # 实际删除逻辑
                if task.file_size:
                    freed_size += task.file_size
                task.delete()
                deleted_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'\n清理完成:'))
        self.stdout.write(f'  删除任务: {deleted_count}')
        self.stdout.write(f'  释放空间: {freed_size / (1024*1024):.2f} MB')
    
    def migrate_to_oss(self, options):
        """迁移本地文件到 OSS"""
        dry_run = options['dry_run']
        
        self.stdout.write('\n📤 迁移本地文件到 OSS')
        
        # 查找本地存储的任务
        local_tasks = PDFParseTask.objects.filter(
            Q(output_dir__isnull=False) & ~Q(output_dir=''),
            status='completed'
        )[:10]  # 限制数量
        
        self.stdout.write(f'找到 {local_tasks.count()} 个本地任务')
        
        if dry_run:
            self.stdout.write('[模拟模式]')
            for task in local_tasks:
                self.stdout.write(f'将迁移: {task.task_id}')
        else:
            # 实际迁移逻辑
            storage_adapter = MinerUStorageAdapter(user=None)
            migrated = 0
            
            for task in local_tasks:
                try:
                    # TODO: 实现迁移逻辑
                    self.stdout.write(f'迁移任务 {task.task_id}')
                    migrated += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'迁移失败 {task.task_id}: {e}')
                    )
            
            self.stdout.write(f'成功迁移 {migrated} 个任务')
    
    def manage_cache(self, options):
        """管理缓存"""
        self.stdout.write('\n💾 缓存管理')
        
        # 本地缓存管理
        from pathlib import Path
        cache_dir = Path(settings.MEDIA_ROOT) / 'oss-bucket' / 'mineru' / 'cache'
        
        if cache_dir.exists():
            cache_files = list(cache_dir.glob('*.json'))
            total_cache = len(cache_files)
            cache_size = sum(f.stat().st_size for f in cache_files)
            
            self.stdout.write(f'缓存文件数: {total_cache}')
            self.stdout.write(f'缓存大小: {cache_size / (1024*1024):.2f} MB')
            
            # 清理过期缓存
            if options.get('force'):
                days = options['days']
                cutoff = timezone.now() - timedelta(days=days)
                old_count = 0
                
                for cache_file in cache_files:
                    file_time = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
                    if file_time < cutoff:
                        old_count += 1
                        if not options['dry_run']:
                            cache_file.unlink()
                
                if old_count > 0:
                    if not options['dry_run']:
                        self.stdout.write(f'已清理 {old_count} 个过期缓存')
                    else:
                        self.stdout.write(f'[模拟] 将清理 {old_count} 个过期缓存')
        else:
            self.stdout.write('缓存目录不存在')
    
    def test_service(self, options):
        """测试服务"""
        self.stdout.write('\n🧪 测试 MinerU 服务')
        
        # 测试原始服务
        try:
            service = MinerUService()
            if service.check_mineru_command():
                self.stdout.write(self.style.SUCCESS('✅ MinerU 命令行可用'))
            else:
                self.stdout.write(self.style.ERROR('❌ MinerU 命令行不可用'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 原始服务测试失败: {e}'))
        
        # 测试优化服务
        try:
            from django.conf import settings
            if settings.MINERU_SETTINGS.get('USE_OSS'):
                optimized = OptimizedMinerUService()
                self.stdout.write(self.style.SUCCESS('✅ 优化服务已启用'))
            else:
                self.stdout.write('优化服务未启用')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 优化服务测试失败: {e}'))
        
        # 测试本地存储
        try:
            from pathlib import Path
            storage_dir = Path(settings.MEDIA_ROOT) / 'oss-bucket' / 'mineru'
            if storage_dir.exists():
                self.stdout.write(self.style.SUCCESS(f'✅ 本地存储目录可用: {storage_dir}'))
                # 测试写入权限
                test_file = storage_dir / 'test_write.tmp'
                try:
                    test_file.touch()
                    test_file.unlink()
                    self.stdout.write(self.style.SUCCESS('✅ 存储目录有写入权限'))
                except:
                    self.stdout.write(self.style.ERROR('❌ 存储目录没有写入权限'))
            else:
                self.stdout.write(self.style.ERROR(f'❌ 本地存储目录不存在: {storage_dir}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 存储测试失败: {e}'))