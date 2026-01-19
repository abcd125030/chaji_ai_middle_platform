#!/usr/bin/env python
"""
测试 MinerU Celery 任务执行
验证异步任务队列是否能正常处理文档
"""

import os
import sys
import django
from pathlib import Path
import time

# Django 环境设置
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from mineru.models import PDFParseTask, ParseResult
from mineru.tasks import process_document_task
from mineru.services.optimized_service import OptimizedMinerUService
from celery.result import AsyncResult

User = get_user_model()


def test_celery_task():
    """测试 Celery 任务执行"""
    
    # 测试文件路径
    test_file_path = '/Users/chagee/Downloads/生产&服务操作手册/服务操作手册 1、概览0620.pdf'
    
    print("=" * 60)
    print("MinerU Celery 任务测试")
    print("=" * 60)
    print(f"\n📄 测试文件: {test_file_path}")
    
    # 检查文件是否存在
    if not os.path.exists(test_file_path):
        print(f"❌ 文件不存在: {test_file_path}")
        return
    
    # 获取文件信息
    file_size = os.path.getsize(test_file_path)
    file_name = os.path.basename(test_file_path)
    print(f"文件名: {file_name}")
    print(f"文件大小: {file_size / (1024*1024):.2f} MB")
    
    # 读取文件内容
    with open(test_file_path, 'rb') as f:
        file_bytes = f.read()
    
    print("\n" + "=" * 60)
    print("步骤 1: 创建测试任务")
    print("=" * 60)
    
    # 获取或创建测试用户
    try:
        user = User.objects.get(username='caijia')
    except User.DoesNotExist:
        user = User.objects.first()
        if not user:
            print("❌ 没有找到用户，请先创建用户")
            return
    print(f"✅ 使用用户: {user.username}")
    
    # 创建任务记录
    task = PDFParseTask.objects.create(
        user=user,
        original_filename=file_name,
        file_type='pdf',
        file_size=file_size,
        parse_method='auto',
        debug_enabled=False,
        enable_table_merge=True,
        use_new_table_model=True,
        status='pending'
    )
    
    print(f"✅ 创建任务: {task.task_id}")
    print(f"   状态: {task.get_status_display()}")
    
    print("\n" + "=" * 60)
    print("步骤 2: 保存文件到适当位置")
    print("=" * 60)
    
    use_oss = settings.MINERU_SETTINGS.get('USE_OSS', False)
    print(f"USE_OSS 配置: {use_oss}")
    
    if use_oss:
        # 使用优化服务保存文件到 OSS
        print("📤 上传文件到 OSS...")
        service = OptimizedMinerUService()
        storage = service._get_storage_adapter(user)
        oss_key, _ = storage.save_upload_file(
            file_bytes=file_bytes,
            filename=file_name,
            task_id=str(task.task_id)
        )
        task.file_path = oss_key
        print(f"✅ 文件已上传到 OSS: {oss_key}")
    else:
        # 保存到本地
        print("💾 保存文件到本地...")
        upload_dir = Path(settings.MEDIA_ROOT) / 'mineru' / 'uploads' / str(task.task_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        local_path = upload_dir / file_name
        
        with open(local_path, 'wb') as f:
            f.write(file_bytes)
        
        # 保存相对路径
        task.file_path = str(local_path.relative_to(settings.MEDIA_ROOT))
        print(f"✅ 文件已保存到本地: {task.file_path}")
    
    task.save()
    
    print("\n" + "=" * 60)
    print("步骤 3: 提交 Celery 任务")
    print("=" * 60)
    
    # 提交异步任务
    print(f"🚀 提交任务到 Celery 队列...")
    result = process_document_task.delay(str(task.task_id))
    print(f"✅ 任务已提交，Celery 任务 ID: {result.id}")
    
    print("\n" + "=" * 60)
    print("步骤 4: 等待任务完成")
    print("=" * 60)
    
    # 等待任务完成（最多等待60秒）
    max_wait = 60
    wait_interval = 2
    elapsed = 0
    
    while elapsed < max_wait:
        # 刷新任务状态
        task.refresh_from_db()
        
        # 检查 Celery 任务状态
        celery_result = AsyncResult(result.id)
        
        print(f"⏳ [{elapsed}s] 任务状态: {task.get_status_display()}, Celery状态: {celery_result.state}")
        
        if task.status == 'completed':
            print("✅ 任务完成！")
            break
        elif task.status == 'failed':
            print(f"❌ 任务失败: {task.error_message}")
            break
        elif celery_result.state == 'FAILURE':
            print(f"❌ Celery 任务失败: {celery_result.info}")
            break
        
        time.sleep(wait_interval)
        elapsed += wait_interval
    
    if elapsed >= max_wait:
        print("⚠️  任务执行超时")
    
    print("\n" + "=" * 60)
    print("步骤 5: 检查任务结果")
    print("=" * 60)
    
    # 重新加载任务
    task.refresh_from_db()
    
    print(f"\n📋 任务最终状态:")
    print(f"   任务ID: {task.task_id}")
    print(f"   状态: {task.get_status_display()}")
    print(f"   文件路径: {task.file_path or '未设置'}")
    print(f"   输出目录: {task.output_dir or '未设置'}")
    if task.processing_time:
        print(f"   处理时间: {task.processing_time:.2f} 秒")
    
    # 检查解析结果
    if hasattr(task, 'result'):
        parse_result = task.result
        print(f"\n📊 解析结果:")
        print(f"   Markdown路径: {parse_result.markdown_path or '未设置'}")
        print(f"   JSON路径: {parse_result.json_path or '未设置'}")
        print(f"   文本块数: {parse_result.total_text_blocks}")
        print(f"   图片数: {parse_result.total_images}")
        print(f"   表格数: {parse_result.total_tables}")
        print(f"   跨页表格数: {parse_result.cross_page_tables}")
        
        if parse_result.metadata:
            print(f"\n📦 元数据:")
            if 'cached' in parse_result.metadata:
                print(f"   使用缓存: {parse_result.metadata['cached']}")
            if 'storage_type' in parse_result.metadata:
                print(f"   存储类型: {parse_result.metadata['storage_type']}")
    
    # 如果有文本预览
    if task.text_preview:
        preview = task.text_preview[:200] + '...' if len(task.text_preview) > 200 else task.text_preview
        print(f"\n📖 文本预览:\n{preview}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)
    
    return task


if __name__ == '__main__':
    test_celery_task()