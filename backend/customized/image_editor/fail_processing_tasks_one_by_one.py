#!/usr/bin/env python
"""
将所有处理中的图片编辑任务逐条标记为失败
直连数据库，避免连接池问题
"""
import os
import sys
from pathlib import Path
import time
from datetime import datetime

# 获取backend根目录并添加到路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Django设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from customized.image_editor.models import ImageEditTask
from django.utils import timezone
from django.db import connection

def fail_processing_tasks_one_by_one():
    """逐条将处理中的任务标记为失败"""
    
    # 获取所有处理中任务的ID列表
    print("正在查询处理中的任务...")
    task_ids = list(ImageEditTask.objects.filter(status='processing').values_list('task_id', flat=True))
    task_count = len(task_ids)
    
    if task_count == 0:
        print("没有找到处理中的任务")
        return
    
    print(f"找到 {task_count} 个处理中的任务")
    
    # 确认操作
    confirm = input(f"\n⚠️  警告：即将逐条把 {task_count} 个处理中的任务标记为失败！\n预计耗时：{task_count * 0.05:.1f} 秒\n是否继续？(yes/no): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消")
        return
    
    print("\n开始逐条更新任务状态...")
    print("=" * 50)
    
    success_count = 0
    failed_count = 0
    
    for i, task_id in enumerate(task_ids, 1):
        try:
            # 逐条更新
            task = ImageEditTask.objects.get(task_id=task_id)
            task.status = 'failed'
            task.error_code = 'SYSTEM_TIMEOUT'
            task.error_message = '任务处理超时，系统自动标记为失败'
            task.error_details = 'Task was marked as failed by admin script (one-by-one processing)'
            task.completed_at = timezone.now()
            task.save()
            
            success_count += 1
            
            # 显示进度
            if i % 10 == 0 or i == task_count:
                progress = (i / task_count) * 100
                print(f"进度: {i}/{task_count} ({progress:.1f}%) - 成功: {success_count}, 失败: {failed_count}")
            
            # 间隔 50ms
            time.sleep(0.05)
            
        except Exception as e:
            failed_count += 1
            print(f"✗ 任务 {task_id} 更新失败: {e}")
            # 继续处理下一个
            continue
        
        # 每100个任务关闭一次连接，避免连接长时间占用
        if i % 100 == 0:
            connection.close()
    
    print("=" * 50)
    print(f"\n✅ 处理完成！")
    print(f"  - 成功更新: {success_count} 个任务")
    print(f"  - 更新失败: {failed_count} 个任务")
    
    # 显示更新后的统计
    print("\n当前任务状态统计：")
    processing_count = ImageEditTask.objects.filter(status='processing').count()
    success_status_count = ImageEditTask.objects.filter(status='success').count()
    failed_status_count = ImageEditTask.objects.filter(status='failed').count()
    total_count = ImageEditTask.objects.count()
    
    print(f"  - 处理中: {processing_count}")
    print(f"  - 成功: {success_status_count}")
    print(f"  - 失败: {failed_status_count}")
    print(f"  - 总计: {total_count}")

if __name__ == "__main__":
    fail_processing_tasks_one_by_one()