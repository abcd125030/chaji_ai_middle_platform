#!/usr/bin/env python
"""
简单的查询脚本，可以直接在服务器上运行
使用方法：
cd /www/wwwroot/repos/X/backend
source .venv/bin/activate
python customized/image_editor/query_errors_simple.py
"""

import os
import sys
import django

# 设置 Django 环境
sys.path.insert(0, '/www/wwwroot/repos/X/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from customized.image_editor.models import ImageEditTask
from django.db.models import Q
from datetime import datetime, timedelta


def main():
    print("\n" + "=" * 60)
    print("ImageEditTask 错误统计")
    print("=" * 60)
    
    # 基础统计
    total = ImageEditTask.objects.count()
    failed = ImageEditTask.objects.filter(status='failed').count()
    
    print(f"\n总任务数: {total}")
    print(f"失败任务数: {failed}")
    
    # 核心查询：port=443 错误
    port_443 = ImageEditTask.objects.filter(
        error_details__icontains='port=443'
    ).count()
    print(f"\n包含 'port=443' 的错误数: {port_443}")
    
    # 核心查询：429 错误
    error_429 = ImageEditTask.objects.filter(
        Q(error_details__icontains='429') | 
        Q(error_message__icontains='429') |
        Q(error_code='429')
    ).count()
    print(f"包含 '429' 的错误数: {error_429}")
    
    # 如果有数据，显示样例
    if port_443 > 0:
        print("\nport=443 错误样例:")
        sample = ImageEditTask.objects.filter(
            error_details__icontains='port=443'
        ).first()
        if sample:
            print(f"  Task ID: {sample.task_id}")
            print(f"  错误详情: {sample.error_details[:200] if sample.error_details else 'N/A'}...")
    
    if error_429 > 0:
        print("\n429 错误样例:")
        sample = ImageEditTask.objects.filter(
            error_details__icontains='429'
        ).first()
        if sample:
            print(f"  Task ID: {sample.task_id}")
            print(f"  错误详情: {sample.error_details[:200] if sample.error_details else 'N/A'}...")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()