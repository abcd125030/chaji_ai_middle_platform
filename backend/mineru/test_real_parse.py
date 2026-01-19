#!/usr/bin/env python
"""
测试真实的 MinerU 解析（不使用缓存）
"""

import os
import sys
import django
from pathlib import Path

# Django 环境设置
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from mineru.models import PDFParseTask
from mineru.services.optimized_service import OptimizedMinerUService
import hashlib

User = get_user_model()


def test_real_parse():
    """测试真实解析，跳过缓存"""
    
    # 测试文件
    test_file_path = '/Users/chagee/Downloads/生产&服务操作手册/服务操作手册 1、概览0620.pdf'
    
    print("=" * 60)
    print("MinerU 真实解析测试（不使用缓存）")
    print("=" * 60)
    
    if not os.path.exists(test_file_path):
        print(f"❌ 文件不存在: {test_file_path}")
        return
    
    # 读取文件
    with open(test_file_path, 'rb') as f:
        file_bytes = f.read()
    
    file_size = len(file_bytes)
    file_name = os.path.basename(test_file_path)
    
    print(f"\n📄 测试文件: {file_name}")
    print(f"文件大小: {file_size / (1024*1024):.2f} MB")
    
    # 计算文件哈希
    file_hash = hashlib.md5(file_bytes).hexdigest()
    print(f"文件哈希: {file_hash}")
    
    # 获取用户
    user = User.objects.get(username='caijia')
    print(f"使用用户: {user.username}")
    
    # 创建新任务（使用不同的文件名避免缓存）
    import uuid
    unique_name = f"test_{uuid.uuid4().hex[:8]}_{file_name}"
    
    task = PDFParseTask.objects.create(
        user=user,
        original_filename=unique_name,  # 使用唯一名称
        file_type='pdf',
        file_size=file_size,
        parse_method='auto',
        debug_enabled=True,  # 开启调试
        enable_table_merge=True,
        use_new_table_model=True,
        status='pending'
    )
    
    print(f"\n✅ 创建任务: {task.task_id}")
    
    # 创建服务并强制不使用缓存
    service = OptimizedMinerUService()
    
    # 临时修改文件内容的哈希（添加时间戳）使其不匹配缓存
    import time
    modified_bytes = file_bytes + str(time.time()).encode()
    
    print("\n🔄 开始解析（跳过缓存）...")
    
    try:
        result = service.process_document(task, modified_bytes)
        
        print("\n✅ 解析完成！")
        print(f"存储类型: {result.get('storage_type', 'unknown')}")
        print(f"处理时间: {result.get('processing_time', 0):.2f} 秒")
        
        if 'stats' in result:
            stats = result['stats']
            print(f"\n📊 解析统计:")
            print(f"   文本块: {stats.get('total_text_blocks', 0)}")
            print(f"   图片数: {stats.get('total_images', 0)}")
            print(f"   表格数: {stats.get('total_tables', 0)}")
            print(f"   跨页表格: {stats.get('cross_page_tables', 0)}")
        
        if 'text_preview' in result:
            print(f"\n📖 文本预览:")
            print("-" * 40)
            print(result['text_preview'][:500])
            print("-" * 40)
        
        if 'urls' in result and result['urls']:
            print(f"\n🔗 生成的文件 URLs:")
            for path, url in list(result['urls'].items())[:5]:
                print(f"   - {path}: {url}")
        
    except Exception as e:
        print(f"\n❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    test_real_parse()