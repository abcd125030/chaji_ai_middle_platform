#!/usr/bin/env python
"""
数据库架构检查脚本
用于验证生产环境的数据库表结构
"""

import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection
from django.apps import apps

def check_table_columns(app_label, model_name):
    """检查指定模型的数据库表结构"""
    try:
        model = apps.get_model(app_label, model_name)
        table_name = model._meta.db_table
        
        with connection.cursor() as cursor:
            # PostgreSQL查询表结构
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, [table_name])
            
            columns = cursor.fetchall()
            
            print(f"\n=== {app_label}.{model_name} ({table_name}) ===")
            print(f"{'Column':<30} {'Type':<20} {'Nullable':<10}")
            print("-" * 60)
            
            for col_name, data_type, is_nullable in columns:
                print(f"{col_name:<30} {data_type:<20} {is_nullable:<10}")
            
            # 检查关键字段
            column_names = [col[0] for col in columns]
            required_fields = ['task_id', 'is_complete', 'session_id', 'created_at']
            
            print("\n字段检查:")
            for field in required_fields:
                if field in column_names:
                    print(f"  ✓ {field} 存在")
                else:
                    print(f"  ✗ {field} 缺失")
            
            return column_names
            
    except Exception as e:
        print(f"检查失败: {e}")
        return []

def check_migrations_status():
    """检查迁移状态"""
    from django.core.management import call_command
    from io import StringIO
    
    print("\n=== 迁移状态 ===")
    output = StringIO()
    call_command('showmigrations', 'chat', stdout=output)
    migrations = output.getvalue()
    print(migrations)
    
    # 检查未应用的迁移
    if '[ ]' in migrations:
        print("⚠️ 有未应用的迁移！")
    else:
        print("✓ 所有迁移已应用")

if __name__ == '__main__':
    print("检查数据库架构...")
    print("=" * 70)
    
    # 检查ChatMessage表结构
    check_table_columns('chat', 'ChatMessage')
    
    # 检查ChatSession表结构
    check_table_columns('chat', 'ChatSession')
    
    # 检查迁移状态
    check_migrations_status()
    
    print("\n" + "=" * 70)
    print("检查完成")