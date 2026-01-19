#!/usr/bin/env python
"""
删除所有图片编辑任务的脚本
警告：此操作不可逆，请谨慎使用！
"""
import os
import sys
from pathlib import Path

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

from customized.image_editor.models import ImageEditTask, BatchTask
from django.conf import settings
import shutil

def delete_all_image_edit_tasks():
    """删除所有图片编辑任务及相关文件"""
    
    # 获取任务数量
    task_count = ImageEditTask.objects.count()
    batch_count = BatchTask.objects.count()
    
    if task_count == 0 and batch_count == 0:
        print("没有找到任何任务需要删除")
        return
    
    print(f"找到 {task_count} 个图片编辑任务")
    print(f"找到 {batch_count} 个批量任务")
    
    # 确认删除
    confirm = input(f"\n⚠️  警告：即将删除 {task_count} 个图片编辑任务和 {batch_count} 个批量任务！\n此操作不可逆！是否继续？(yes/no): ")
    
    if confirm.lower() != 'yes':
        print("操作已取消")
        return
    
    # 再次确认
    confirm2 = input("\n请再次确认，输入 'DELETE ALL' 继续: ")
    
    if confirm2 != 'DELETE ALL':
        print("操作已取消")
        return
    
    print("\n开始删除任务...")
    
    # 1. 删除相关的图片文件
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
    
    # 2. 删除数据库中的任务记录
    try:
        # 删除所有ImageEditTask记录
        deleted_tasks = ImageEditTask.objects.all().delete()
        print(f"✓ 已删除 {deleted_tasks[0]} 个图片编辑任务")
        
        # 删除所有BatchTask记录
        deleted_batches = BatchTask.objects.all().delete()
        print(f"✓ 已删除 {deleted_batches[0]} 个批量任务")
        
    except Exception as e:
        print(f"✗ 删除数据库记录失败: {e}")
        return
    
    # 3. 清理Redis缓存（如果需要）
    try:
        from customized.image_editor.cache_manager import TaskCacheManager
        from django.core.cache import cache
        
        # 清理所有任务缓存
        # 注意：这将清理所有以 'task:' 开头的缓存键
        cache_pattern = 'task:*'
        print(f"清理Redis缓存 (pattern: {cache_pattern})")
        
        # Django cache不支持模式删除，所以我们需要另一种方法
        # 如果使用的是redis缓存后端，可以直接操作
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            keys = redis_conn.keys('task:*')
            if keys:
                redis_conn.delete(*keys)
                print(f"✓ 已清理 {len(keys)} 个缓存键")
            else:
                print("✓ 没有找到需要清理的缓存")
        except ImportError:
            print("⚠ 未安装django-redis，跳过缓存清理")
        except Exception as e:
            print(f"⚠ 清理缓存时出错: {e}")
            
    except Exception as e:
        print(f"⚠ 处理缓存时出错: {e}")
    
    print("\n✅ 所有任务删除完成！")
    
    # 显示删除后的状态
    remaining_tasks = ImageEditTask.objects.count()
    remaining_batches = BatchTask.objects.count()
    print(f"\n当前状态:")
    print(f"- 图片编辑任务数: {remaining_tasks}")
    print(f"- 批量任务数: {remaining_batches}")

if __name__ == "__main__":
    delete_all_image_edit_tasks()