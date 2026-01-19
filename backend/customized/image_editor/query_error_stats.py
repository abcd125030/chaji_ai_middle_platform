#!/usr/bin/env python
"""
查询 ImageEditTask 数据库中 error_details 字段的统计信息
"""
import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, '/Users/chagee/Repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from customized.image_editor.models import ImageEditTask
from django.db.models import Q, Count
from datetime import datetime, timedelta


def query_error_stats():
    """查询错误详情中包含特定关键词的统计信息"""
    
    # 获取所有任务总数
    total_tasks = ImageEditTask.objects.count()
    print(f"总任务数: {total_tasks}")
    
    # 获取失败任务总数
    failed_tasks = ImageEditTask.objects.filter(status='failed').count()
    print(f"失败任务数: {failed_tasks}")
    
    # 统计包含 port=443 的错误（连接错误）
    port_443_errors = ImageEditTask.objects.filter(
        error_details__icontains='port=443'
    ).count()
    print(f"\n包含 'port=443' 的错误数（连接相关）: {port_443_errors}")
    
    # 统计包含 429 的错误（通常是 Too Many Requests）
    error_429 = ImageEditTask.objects.filter(
        error_details__icontains='429'
    ).count()
    print(f"包含 '429' 的错误数（请求过多）: {error_429}")
    
    # 获取更详细的错误分析
    print("\n详细错误分析:")
    print("-" * 50)
    
    # 查看最近的 port=443 错误样例
    recent_443_errors = ImageEditTask.objects.filter(
        error_details__icontains='port=443'
    ).order_by('-created_at')[:3]
    
    if recent_443_errors:
        print("\n最近的 port=443 错误样例:")
        for task in recent_443_errors:
            print(f"  Task ID: {task.task_id}")
            print(f"  创建时间: {task.created_at}")
            print(f"  错误信息: {task.error_message[:100] if task.error_message else 'N/A'}...")
            print(f"  错误详情摘要: {task.error_details[:200] if task.error_details else 'N/A'}...")
            print("-" * 30)
    
    # 查看最近的 429 错误样例
    recent_429_errors = ImageEditTask.objects.filter(
        error_details__icontains='429'
    ).order_by('-created_at')[:3]
    
    if recent_429_errors:
        print("\n最近的 429 错误样例:")
        for task in recent_429_errors:
            print(f"  Task ID: {task.task_id}")
            print(f"  创建时间: {task.created_at}")
            print(f"  错误信息: {task.error_message[:100] if task.error_message else 'N/A'}...")
            print(f"  错误详情摘要: {task.error_details[:200] if task.error_details else 'N/A'}...")
            print("-" * 30)
    
    # 按时间段统计错误
    print("\n过去7天的错误分布:")
    seven_days_ago = datetime.now() - timedelta(days=7)
    
    recent_443 = ImageEditTask.objects.filter(
        created_at__gte=seven_days_ago,
        error_details__icontains='port=443'
    ).count()
    
    recent_429 = ImageEditTask.objects.filter(
        created_at__gte=seven_days_ago,
        error_details__icontains='429'
    ).count()
    
    print(f"  port=443 错误: {recent_443}")
    print(f"  429 错误: {recent_429}")
    
    # 其他常见错误模式
    print("\n其他错误模式统计:")
    
    # 超时错误
    timeout_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='timeout') | 
        Q(error_details__icontains='timed out')
    ).count()
    print(f"  超时错误: {timeout_errors}")
    
    # 连接错误
    connection_errors = ImageEditTask.objects.filter(
        Q(error_details__icontains='connection') |
        Q(error_details__icontains='connect')
    ).count()
    print(f"  连接错误: {connection_errors}")
    
    # SSL 错误
    ssl_errors = ImageEditTask.objects.filter(
        error_details__icontains='ssl'
    ).count()
    print(f"  SSL 错误: {ssl_errors}")
    
    return {
        'total_tasks': total_tasks,
        'failed_tasks': failed_tasks,
        'port_443_errors': port_443_errors,
        'error_429': error_429,
        'recent_443': recent_443,
        'recent_429': recent_429
    }


if __name__ == '__main__':
    print("=" * 60)
    print("ImageEditTask 错误统计分析")
    print("=" * 60)
    
    stats = query_error_stats()
    
    print("\n" + "=" * 60)
    print("统计结果汇总:")
    print(f"  总任务数: {stats['total_tasks']}")
    print(f"  失败任务数: {stats['failed_tasks']}")
    print(f"  包含 port=443 的错误: {stats['port_443_errors']}")
    print(f"  包含 429 的错误: {stats['error_429']}")
    print("=" * 60)