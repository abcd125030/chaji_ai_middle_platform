#!/usr/bin/env python
"""
清理 object_storage 应用的数据库记录

背景：
    项目已从 object_storage 模块迁移到本地文件系统存储（media/oss-bucket）。
    虽然代码和应用已删除，但数据库中仍可能存在相关记录需要清理。

清理内容：
    - django_admin_log 表中的相关记录
    - auth_permission 表中的权限记录  
    - django_content_type 表中的内容类型记录
    - django_migrations 表中的迁移记录

服务器部署时使用方法：
    # 1. 进入项目目录
    cd /path/to/X/backend
    
    # 2. 激活虚拟环境
    source .venv/bin/activate
    
    # 3. 查看将要删除的记录（不实际删除）
    python backend/utils/cleanup_object_storage.py --dry-run
    
    # 4. 执行实际清理（需要输入 yes 确认）
    python backend/utils/cleanup_object_storage.py
    
    # 5. 执行实际清理（跳过确认，适合自动化脚本）
    python backend/utils/cleanup_object_storage.py --force

注意事项：
    - 执行前请确保已备份数据库
    - 清理操作在事务中执行，失败会自动回滚
    - 清理顺序已考虑外键依赖关系
"""

import os
import sys
import django

# 添加项目路径（backend 目录的父目录）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection, transaction


def check_records():
    """检查需要清理的记录"""
    records = {
        'admin_logs': 0,
        'migrations': 0,
        'content_types': 0,
        'permissions': 0,
        'total': 0
    }
    
    with connection.cursor() as cursor:
        # 检查管理日志记录
        cursor.execute("""
            SELECT COUNT(*) FROM django_admin_log 
            WHERE content_type_id IN (
                SELECT id FROM django_content_type 
                WHERE app_label = %s
            )
        """, ['object_storage'])
        records['admin_logs'] = cursor.fetchone()[0]
        
        # 检查迁移记录
        cursor.execute(
            "SELECT COUNT(*) FROM django_migrations WHERE app = %s",
            ['object_storage']
        )
        records['migrations'] = cursor.fetchone()[0]
        
        # 检查 ContentType
        cursor.execute(
            "SELECT COUNT(*) FROM django_content_type WHERE app_label = %s",
            ['object_storage']
        )
        records['content_types'] = cursor.fetchone()[0]
        
        # 检查权限
        cursor.execute("""
            SELECT COUNT(*) FROM auth_permission 
            WHERE content_type_id IN (
                SELECT id FROM django_content_type 
                WHERE app_label = %s
            )
        """, ['object_storage'])
        records['permissions'] = cursor.fetchone()[0]
    
    records['total'] = sum([
        records['admin_logs'],
        records['migrations'],
        records['content_types'],
        records['permissions']
    ])
    
    return records


def cleanup_records():
    """执行清理操作"""
    deleted_counts = {
        'admin_logs': 0,
        'permissions': 0,
        'content_types': 0,
        'migrations': 0
    }
    
    with transaction.atomic():
        with connection.cursor() as cursor:
            # 1. 删除管理日志（最先删除，因为它引用 content_type）
            cursor.execute("""
                DELETE FROM django_admin_log 
                WHERE content_type_id IN (
                    SELECT id FROM django_content_type 
                    WHERE app_label = %s
                )
            """, ['object_storage'])
            deleted_counts['admin_logs'] = cursor.rowcount
            
            # 2. 删除权限（依赖 content_type）
            cursor.execute("""
                DELETE FROM auth_permission 
                WHERE content_type_id IN (
                    SELECT id FROM django_content_type 
                    WHERE app_label = %s
                )
            """, ['object_storage'])
            deleted_counts['permissions'] = cursor.rowcount
            
            # 3. 删除 ContentType
            cursor.execute(
                "DELETE FROM django_content_type WHERE app_label = %s",
                ['object_storage']
            )
            deleted_counts['content_types'] = cursor.rowcount
            
            # 4. 删除迁移记录
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = %s",
                ['object_storage']
            )
            deleted_counts['migrations'] = cursor.rowcount
    
    return deleted_counts


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='清理 object_storage 应用的数据库记录')
    parser.add_argument('--dry-run', action='store_true', 
                        help='只显示将要删除的内容，不实际执行删除操作')
    parser.add_argument('--force', action='store_true',
                        help='跳过确认直接执行')
    
    args = parser.parse_args()
    
    print('正在检查 object_storage 相关的数据库记录...')
    print('='*50)
    
    # 检查记录
    records = check_records()
    
    if not records['total']:
        print('✅ 没有找到需要清理的记录')
        return 0
    
    # 显示将要清理的内容
    print('找到以下需要清理的记录：')
    print('-'*50)
    
    if records['admin_logs']:
        print(f"📝 django_admin_log 表: {records['admin_logs']} 条记录")
    
    if records['migrations']:
        print(f"📋 django_migrations 表: {records['migrations']} 条记录")
    
    if records['content_types']:
        print(f"📦 django_content_type 表: {records['content_types']} 条记录")
    
    if records['permissions']:
        print(f"🔑 auth_permission 表: {records['permissions']} 条记录")
    
    print('-'*50)
    print(f"总计: {records['total']} 条记录")
    print('='*50)
    
    if args.dry_run:
        print('\n⚠️  DRY RUN 模式：以上记录不会被删除')
        print('\n在生产环境执行实际清理时，请运行：')
        print('DJANGO_SETTINGS_MODULE=backend.settings python backend/utils/cleanup_object_storage.py --force')
        return 0
    
    # 确认删除
    if not args.force:
        confirm = input('\n确定要删除这些记录吗？(yes/no): ')
        if confirm.lower() != 'yes':
            print('操作已取消')
            return 0
    
    # 执行清理
    try:
        print('\n开始清理...')
        deleted = cleanup_records()
        
        print('\n清理结果：')
        print('-'*50)
        
        if deleted['admin_logs']:
            print(f"✓ 删除了 {deleted['admin_logs']} 条管理日志记录")
        
        if deleted['permissions']:
            print(f"✓ 删除了 {deleted['permissions']} 条权限记录")
        
        if deleted['content_types']:
            print(f"✓ 删除了 {deleted['content_types']} 条 ContentType 记录")
        
        if deleted['migrations']:
            print(f"✓ 删除了 {deleted['migrations']} 条迁移记录")
        
        print('='*50)
        print('✅ 清理完成！')
        
        # 验证清理结果
        remaining = check_records()
        if remaining['total'] > 0:
            print(f'\n⚠️  警告：仍有 {remaining["total"]} 条记录未清理')
            return 1
        
        return 0
        
    except Exception as e:
        print(f'\n❌ 清理失败：{str(e)}')
        return 1


if __name__ == '__main__':
    sys.exit(main())