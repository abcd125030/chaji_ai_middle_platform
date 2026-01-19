"""
Django management command for querying ImageEditTask errors
Usage: python manage.py query_errors
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from datetime import datetime, timedelta
from customized.image_editor.models import ImageEditTask


class Command(BaseCommand):
    help = 'Query and analyze ImageEditTask errors'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("ImageEditTask 错误详情统计分析")
        self.stdout.write("=" * 80)
        
        # 基础统计
        total_tasks = ImageEditTask.objects.count()
        processing_tasks = ImageEditTask.objects.filter(status='processing').count()
        success_tasks = ImageEditTask.objects.filter(status='success').count()
        failed_tasks = ImageEditTask.objects.filter(status='failed').count()
        
        self.stdout.write(f"\n📊 任务状态统计:")
        self.stdout.write(f"  总任务数: {total_tasks}")
        self.stdout.write(f"  处理中: {processing_tasks}")
        self.stdout.write(f"  成功: {success_tasks}")
        self.stdout.write(f"  失败: {failed_tasks}")
        if total_tasks > 0:
            self.stdout.write(f"  失败率: {failed_tasks/total_tasks*100:.2f}%")
        
        # 关键错误类型统计
        self.stdout.write(f"\n🔍 关键错误类型统计:")
        
        # port=443 相关错误
        port_443_count = ImageEditTask.objects.filter(
            error_details__icontains='port=443'
        ).count()
        self.stdout.write(f"\n  1. 包含 'port=443' 的错误（连接错误）: {port_443_count}")
        
        # 429 错误
        error_429_count = ImageEditTask.objects.filter(
            Q(error_details__icontains='429') | 
            Q(error_message__icontains='429') |
            Q(error_code='429')
        ).count()
        self.stdout.write(f"  2. 包含 '429' 的错误（速率限制）: {error_429_count}")
        
        # 时间分布分析
        self.stdout.write(f"\n📅 时间分布分析:")
        
        # 最近24小时
        one_day_ago = datetime.now() - timedelta(days=1)
        recent_24h_443 = ImageEditTask.objects.filter(
            created_at__gte=one_day_ago,
            error_details__icontains='port=443'
        ).count()
        recent_24h_429 = ImageEditTask.objects.filter(
            created_at__gte=one_day_ago,
            error_details__icontains='429'
        ).count()
        
        self.stdout.write(f"  过去24小时:")
        self.stdout.write(f"    port=443 错误: {recent_24h_443}")
        self.stdout.write(f"    429 错误: {recent_24h_429}")
        
        # 最近7天
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_7d_443 = ImageEditTask.objects.filter(
            created_at__gte=seven_days_ago,
            error_details__icontains='port=443'
        ).count()
        recent_7d_429 = ImageEditTask.objects.filter(
            created_at__gte=seven_days_ago,
            error_details__icontains='429'
        ).count()
        
        self.stdout.write(f"  过去7天:")
        self.stdout.write(f"    port=443 错误: {recent_7d_443}")
        self.stdout.write(f"    429 错误: {recent_7d_429}")
        
        # 其他错误模式
        self.stdout.write(f"\n🔧 其他错误模式统计:")
        
        timeout_errors = ImageEditTask.objects.filter(
            Q(error_details__icontains='timeout') | 
            Q(error_details__icontains='timed out')
        ).count()
        self.stdout.write(f"  超时错误: {timeout_errors}")
        
        connection_errors = ImageEditTask.objects.filter(
            Q(error_details__icontains='connection') |
            Q(error_details__icontains='connect')
        ).exclude(error_details__icontains='port=443').count()
        self.stdout.write(f"  其他连接错误: {connection_errors}")
        
        ssl_errors = ImageEditTask.objects.filter(
            Q(error_details__icontains='ssl') |
            Q(error_details__icontains='tls')
        ).count()
        self.stdout.write(f"  SSL/TLS 错误: {ssl_errors}")
        
        # 获取错误样例
        self.stdout.write(f"\n📝 错误样例（最近5条失败任务）:")
        self.stdout.write("-" * 80)
        
        recent_failures = ImageEditTask.objects.filter(
            status='failed'
        ).exclude(
            error_details__isnull=True
        ).exclude(
            error_details=''
        ).order_by('-created_at')[:5]
        
        for idx, task in enumerate(recent_failures, 1):
            self.stdout.write(f"\n样例 {idx}:")
            self.stdout.write(f"  Task ID: {task.task_id}")
            self.stdout.write(f"  创建时间: {task.created_at}")
            self.stdout.write(f"  错误码: {task.error_code or 'N/A'}")
            
            if task.error_details:
                patterns = []
                if 'port=443' in task.error_details:
                    patterns.append('port=443')
                if '429' in task.error_details:
                    patterns.append('429')
                if patterns:
                    self.stdout.write(f"  包含模式: {', '.join(patterns)}")
                self.stdout.write(f"  错误详情前200字符:")
                self.stdout.write(f"  {task.error_details[:200]}...")
        
        # 总结
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📊 统计总结")
        self.stdout.write("=" * 80)
        self.stdout.write(f"总任务数: {total_tasks}")
        self.stdout.write(f"失败任务数: {failed_tasks}")
        self.stdout.write(f"包含 port=443 的错误: {port_443_count}")
        self.stdout.write(f"包含 429 的错误: {error_429_count}")
        self.stdout.write("=" * 80)