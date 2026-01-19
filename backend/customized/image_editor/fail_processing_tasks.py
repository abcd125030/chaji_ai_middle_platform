#!/usr/bin/env python
"""
将所有处理中的图片编辑任务标记为失败
用于清理卡住的任务或系统异常后的恢复
"""
import os
import sys
from pathlib import Path
from datetime import datetime

# 获取backend根目录并添加到路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

# 检查是否需要使用 PgBouncer（通过命令行参数或环境变量）
if '--pgbouncer' in sys.argv or os.getenv('USE_PGBOUNCER', '').lower() == 'true':
    print("✓ 使用 PgBouncer 连接（端口 6432）")
    os.environ['USE_PGBOUNCER'] = 'true'
    os.environ['DB_PORT'] = '6432'
elif os.getenv('DB_PORT') == '6432':
    print("✓ 检测到 PgBouncer 端口配置")
    os.environ['USE_PGBOUNCER'] = 'true'

# Django设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from customized.image_editor.models import ImageEditTask
from django.utils import timezone

def show_usage():
    """显示使用说明"""
    print("""
使用方法:
    python fail_processing_tasks.py [选项]

选项:
    --pgbouncer     使用 PgBouncer 连接（端口 6432）
    --help          显示此帮助信息

环境变量:
    USE_PGBOUNCER=true    启用 PgBouncer 连接
    DB_PORT=6432         自动检测为 PgBouncer 连接

示例:
    # 直连 PostgreSQL
    python fail_processing_tasks.py
    
    # 使用 PgBouncer
    python fail_processing_tasks.py --pgbouncer
    
    # 或通过环境变量
    USE_PGBOUNCER=true python fail_processing_tasks.py
    """)

def fail_all_processing_tasks():
    """将所有处理中的任务标记为失败"""
    
    # 获取所有处理中的任务
    processing_tasks = ImageEditTask.objects.filter(status='processing')
    task_count = processing_tasks.count()
    
    if task_count == 0:
        print("没有找到处理中的任务")
        return
    
    print(f"找到 {task_count} 个处理中的任务")
    
    # 显示部分任务信息
    print("\n前10个任务信息：")
    for task in processing_tasks[:10]:
        print(f"  - Task ID: {task.task_id}")
        print(f"    用户: {task.user}")
        print(f"    创建时间: {task.created_at}")
        print(f"    提示词: {task.prompt[:50]}..." if len(task.prompt) > 50 else f"    提示词: {task.prompt}")
    
    if task_count > 10:
        print(f"  ... 还有 {task_count - 10} 个任务")
    
    # 确认操作
    confirm = input(f"\n⚠️  警告：即将把 {task_count} 个处理中的任务标记为失败！\n是否继续？(yes/no): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消")
        return
    
    print("\n开始更新任务状态...")
    
    # 批量更新任务状态
    try:
        updated_count = processing_tasks.update(
            status='failed',
            error_code='SYSTEM_TIMEOUT',
            error_message='任务处理超时，系统自动标记为失败',
            error_details='Task was marked as failed by admin script due to processing timeout or system recovery',
            completed_at=timezone.now()
        )
        
        print(f"✓ 成功将 {updated_count} 个任务标记为失败")
        
    except Exception as e:
        print(f"✗ 更新任务状态失败: {e}")
        return
    
    # 清理相关缓存（如果有）
    try:
        from customized.image_editor.cache_manager import TaskCacheManager
        
        print("\n清理相关缓存...")
        cache_manager = TaskCacheManager()
        
        # 重新查询已更新的任务
        failed_tasks = ImageEditTask.objects.filter(
            status='failed',
            error_code='SYSTEM_TIMEOUT'
        ).order_by('-completed_at')[:task_count]
        
        cleared_count = 0
        for task in failed_tasks:
            try:
                # 清理任务缓存
                cache_manager.delete_task(str(task.task_id))
                cleared_count += 1
            except:
                pass  # 忽略单个缓存清理失败
        
        if cleared_count > 0:
            print(f"✓ 已清理 {cleared_count} 个任务的缓存")
        
    except ImportError:
        print("⚠ 未找到缓存管理器，跳过缓存清理")
    except Exception as e:
        print(f"⚠ 清理缓存时出错: {e}（不影响任务状态更新）")
    
    print("\n✅ 操作完成！")
    
    # 显示更新后的统计
    print("\n当前任务状态统计：")
    processing_count = ImageEditTask.objects.filter(status='processing').count()
    success_count = ImageEditTask.objects.filter(status='success').count()
    failed_count = ImageEditTask.objects.filter(status='failed').count()
    total_count = ImageEditTask.objects.count()
    
    print(f"  - 处理中: {processing_count}")
    print(f"  - 成功: {success_count}")
    print(f"  - 失败: {failed_count}")
    print(f"  - 总计: {total_count}")

if __name__ == "__main__":
    if '--help' in sys.argv:
        show_usage()
        sys.exit(0)
    
    fail_all_processing_tasks()