#!/usr/bin/env python
"""
清理 Celery 任务结果数据脚本
用于清空或清理 django_celery_results_taskresult 表中的历史数据
"""

import os
import sys
import django
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.utils import timezone
import argparse


def get_table_stats():
    """获取表统计信息"""
    with connection.cursor() as cursor:
        # 获取记录总数
        cursor.execute("""
            SELECT COUNT(*) FROM django_celery_results_taskresult
        """)
        total_count = cursor.fetchone()[0]
        
        # 获取表大小（PostgreSQL）
        try:
            cursor.execute("""
                SELECT pg_size_pretty(pg_total_relation_size('django_celery_results_taskresult'))
            """)
            table_size = cursor.fetchone()[0]
        except:
            table_size = "N/A (非PostgreSQL数据库)"
        
        # 按任务类型分组统计
        cursor.execute("""
            SELECT task_name, COUNT(*) as count
            FROM django_celery_results_taskresult
            GROUP BY task_name
            ORDER BY count DESC
            LIMIT 10
        """)
        task_stats = cursor.fetchall()
        
        return total_count, table_size, task_stats


def clean_by_age(days):
    """清理指定天数之前的记录"""
    cutoff_date = timezone.now() - timedelta(days=days)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            DELETE FROM django_celery_results_taskresult
            WHERE date_done < %s
        """, [cutoff_date])
        
        deleted_count = cursor.rowcount
        
    return deleted_count, cutoff_date


def clean_by_task_name(task_patterns):
    """清理特定任务名称的记录"""
    deleted_total = 0
    
    with connection.cursor() as cursor:
        for pattern in task_patterns:
            cursor.execute("""
                DELETE FROM django_celery_results_taskresult
                WHERE task_name LIKE %s
            """, [f"%{pattern}%"])
            
            deleted_total += cursor.rowcount
            print(f"  删除任务 '{pattern}' 相关记录: {cursor.rowcount} 条")
    
    return deleted_total


def clean_high_frequency_tasks():
    """清理高频任务（已配置 ignore_result 的任务）"""
    high_freq_tasks = [
        'check_and_flush_callbacks',
        'cleanup_stuck_callbacks',
        'trigger_batch_send',
        'send_single_callback',
        'reload_worker_config'
    ]
    
    return clean_by_task_name(high_freq_tasks)


def clean_all():
    """清空所有记录（危险操作）"""
    with connection.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE django_celery_results_taskresult")
        print("已清空所有 Celery 任务结果记录")


def vacuum_table():
    """优化表（仅 PostgreSQL）"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE django_celery_results_taskresult")
            print("已优化表空间")
    except:
        print("表优化失败（可能不是 PostgreSQL 数据库）")


def main():
    parser = argparse.ArgumentParser(description='清理 Celery 任务结果数据')
    parser.add_argument('--mode', choices=['stats', 'age', 'high-freq', 'task', 'all', 'vacuum'],
                        default='stats',
                        help='清理模式: stats(统计), age(按天数), high-freq(高频任务), task(指定任务), all(全部), vacuum(优化表)')
    parser.add_argument('--days', type=int, default=30,
                        help='清理多少天前的数据（仅 age 模式）')
    parser.add_argument('--task-name', type=str,
                        help='要清理的任务名称模式（仅 task 模式）')
    parser.add_argument('--confirm', action='store_true',
                        help='确认执行危险操作')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Celery 任务结果数据清理工具")
    print("=" * 60)
    
    # 先显示当前统计
    print("\n当前数据统计:")
    total_count, table_size, task_stats = get_table_stats()
    print(f"  总记录数: {total_count:,}")
    print(f"  表大小: {table_size}")
    
    if task_stats:
        print("\n  任务类型统计 (Top 10):")
        for task_name, count in task_stats:
            print(f"    - {task_name}: {count:,} 条")
    
    print("\n" + "-" * 60)
    
    # 执行清理操作
    if args.mode == 'stats':
        print("\n仅显示统计信息，未执行清理操作")
        print("\n可用的清理命令:")
        print("  --mode age --days 7        # 清理7天前的数据")
        print("  --mode high-freq           # 清理高频任务")
        print("  --mode task --task-name XX # 清理特定任务")
        print("  --mode all --confirm       # 清空所有数据（危险）")
        print("  --mode vacuum              # 优化表空间")
        
    elif args.mode == 'age':
        print(f"\n准备清理 {args.days} 天前的数据...")
        deleted_count, cutoff_date = clean_by_age(args.days)
        print(f"已删除 {deleted_count:,} 条记录（早于 {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}）")
        
    elif args.mode == 'high-freq':
        print("\n清理高频任务记录...")
        deleted_count = clean_high_frequency_tasks()
        print(f"总共删除 {deleted_count:,} 条高频任务记录")
        
    elif args.mode == 'task':
        if not args.task_name:
            print("错误：task 模式需要指定 --task-name 参数")
            sys.exit(1)
        print(f"\n清理任务 '{args.task_name}' 相关记录...")
        deleted_count = clean_by_task_name([args.task_name])
        print(f"总共删除 {deleted_count:,} 条记录")
        
    elif args.mode == 'all':
        if not args.confirm:
            print("\n⚠️  警告：此操作将清空所有 Celery 任务结果！")
            print("如确认执行，请添加 --confirm 参数")
            sys.exit(1)
        print("\n清空所有记录...")
        clean_all()
        
    elif args.mode == 'vacuum':
        print("\n优化表空间...")
        vacuum_table()
    
    # 显示清理后的统计
    if args.mode != 'stats':
        print("\n" + "-" * 60)
        print("\n清理后数据统计:")
        total_count, table_size, _ = get_table_stats()
        print(f"  总记录数: {total_count:,}")
        print(f"  表大小: {table_size}")
    
    print("\n" + "=" * 60)
    print("操作完成")


if __name__ == "__main__":
    main()