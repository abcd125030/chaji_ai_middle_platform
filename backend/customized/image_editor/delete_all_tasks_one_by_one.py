#!/usr/bin/env python
"""
逐条删除所有图片编辑任务
直连数据库，避免连接池问题
警告：此操作不可逆，请谨慎使用！
"""
import os
import sys
from pathlib import Path
import time
import shutil

# 获取backend根目录并添加到路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# Django设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from customized.image_editor.models import ImageEditTask, BatchTask
from django.conf import settings
from django.db import connection

def delete_all_tasks_one_by_one():
    """逐条删除所有图片编辑任务"""
    
    # 获取所有任务ID
    print("正在查询所有任务...")
    task_ids = list(ImageEditTask.objects.all().values_list('task_id', flat=True))
    batch_ids = list(BatchTask.objects.all().values_list('batch_id', flat=True))
    
    task_count = len(task_ids)
    batch_count = len(batch_ids)
    
    if task_count == 0 and batch_count == 0:
        print("没有找到任何任务需要删除")
        return
    
    print(f"找到 {task_count} 个图片编辑任务")
    print(f"找到 {batch_count} 个批量任务")
    
    total_count = task_count + batch_count
    estimated_time = total_count * 0.05
    
    # 确认删除
    confirm = input(f"\n⚠️  警告：即将逐条删除 {task_count} 个图片编辑任务和 {batch_count} 个批量任务！\n预计耗时：{estimated_time:.1f} 秒\n此操作不可逆！是否继续？(yes/no): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消")
        return
    
    # 再次确认
    confirm2 = input("\n请再次确认，输入 'DELETE ALL' 继续: ")
    
    if confirm2 != 'DELETE ALL':
        print("操作已取消")
        return
    
    print("\n开始逐条删除任务...")
    print("=" * 50)
    
    # 1. 删除图片文件目录
    media_root = getattr(settings, 'MEDIA_ROOT', '/Users/chagee/Repos/X/backend/media')
    image_dir = Path(media_root) / 'image_editor'
    
    if image_dir.exists():
        try:
            file_count = len(list(image_dir.glob('*')))
            print(f"删除图片文件目录: {image_dir} (包含 {file_count} 个文件)")
            shutil.rmtree(image_dir)
            print("✓ 图片文件已删除")
        except Exception as e:
            print(f"✗ 删除图片文件失败: {e}")
    else:
        print("图片目录不存在，跳过文件删除")
    
    print("\n开始删除数据库记录...")
    
    # 2. 逐条删除 ImageEditTask
    deleted_tasks = 0
    failed_tasks = 0
    
    for i, task_id in enumerate(task_ids, 1):
        try:
            task = ImageEditTask.objects.get(task_id=task_id)
            task.delete()
            deleted_tasks += 1
            
            # 显示进度
            if i % 10 == 0 or i == task_count:
                progress = (i / task_count) * 100 if task_count > 0 else 100
                print(f"删除任务进度: {i}/{task_count} ({progress:.1f}%) - 成功: {deleted_tasks}, 失败: {failed_tasks}")
            
            # 间隔 50ms
            time.sleep(0.05)
            
        except Exception as e:
            failed_tasks += 1
            print(f"✗ 任务 {task_id} 删除失败: {e}")
            continue
        
        # 每100个任务关闭一次连接
        if i % 100 == 0:
            connection.close()
    
    # 3. 逐条删除 BatchTask
    deleted_batches = 0
    failed_batches = 0
    
    for i, batch_id in enumerate(batch_ids, 1):
        try:
            batch = BatchTask.objects.get(batch_id=batch_id)
            batch.delete()
            deleted_batches += 1
            
            # 显示进度
            if i % 10 == 0 or i == batch_count:
                progress = (i / batch_count) * 100 if batch_count > 0 else 100
                print(f"删除批量任务进度: {i}/{batch_count} ({progress:.1f}%) - 成功: {deleted_batches}, 失败: {failed_batches}")
            
            # 间隔 50ms
            time.sleep(0.05)
            
        except Exception as e:
            failed_batches += 1
            print(f"✗ 批量任务 {batch_id} 删除失败: {e}")
            continue
        
        # 每100个任务关闭一次连接
        if i % 100 == 0:
            connection.close()
    
    print("=" * 50)
    print(f"\n✅ 删除完成！")
    print(f"  - 成功删除图片编辑任务: {deleted_tasks}/{task_count}")
    print(f"  - 成功删除批量任务: {deleted_batches}/{batch_count}")
    
    if failed_tasks > 0:
        print(f"  - 删除失败的图片编辑任务: {failed_tasks}")
    if failed_batches > 0:
        print(f"  - 删除失败的批量任务: {failed_batches}")
    
    # 显示删除后的状态
    remaining_tasks = ImageEditTask.objects.count()
    remaining_batches = BatchTask.objects.count()
    print(f"\n当前状态:")
    print(f"  - 剩余图片编辑任务数: {remaining_tasks}")
    print(f"  - 剩余批量任务数: {remaining_batches}")
    
    # 清理缓存（如果有）
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        keys = redis_conn.keys('task:*')
        if keys:
            # 逐条删除缓存键
            for key in keys:
                redis_conn.delete(key)
                time.sleep(0.01)  # 10ms 间隔
            print(f"✓ 已清理 {len(keys)} 个缓存键")
        else:
            print("✓ 没有找到需要清理的缓存")
    except ImportError:
        print("⚠ 未安装django-redis，跳过缓存清理")
    except Exception as e:
        print(f"⚠ 清理缓存时出错: {e}")

if __name__ == "__main__":
    delete_all_tasks_one_by_one()