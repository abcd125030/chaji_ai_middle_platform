# Backend 系统升级与数据迁移完整指南

## 概述
本文档提供完整的 backend 系统升级步骤，包括：
1. 用户认证系统升级到多账号体系
2. Pagtive 应用模型创建
3. 从 pagtive_previews 数据库迁移数据

## 一、环境说明

### 本地开发环境
- PostgreSQL: 通过安装包安装（如 Postgres.app）
- 访问方式: `psql -U postgres -d 数据库名`
- 密码: `caijia332335`

### 服务器生产环境
- PostgreSQL: 通过宝塔面板安装
- 访问方式: 
  - 宝塔面板数据库管理界面
  - 或通过 SSH: `psql -h localhost -U postgres -d 数据库名`
- 注意: 需要先 SSH 登录服务器

## 二、升级步骤

### 步骤1：备份数据库（重要！）

#### 本地环境
```bash
pg_dump -h localhost -U postgres -d X > backup_X_$(date +%Y%m%d_%H%M%S).sql
pg_dump -h localhost -U postgres -d pagtive_previews > backup_pagtive_$(date +%Y%m%d_%H%M%S).sql
```

#### 服务器环境
```bash
# SSH 登录服务器后
sudo -u postgres pg_dump X > /backup/backup_X_$(date +%Y%m%d_%H%M%S).sql
sudo -u postgres pg_dump pagtive_previews > /backup/backup_pagtive_$(date +%Y%m%d_%H%M%S).sql
```

### 步骤2：数据库结构迁移

#### 本地环境
```bash
cd /Users/chagee/Repos/X/backend
source .venv/bin/activate

# 生成迁移文件
python manage.py makemigrations authentication
python manage.py makemigrations pagtive

# 应用迁移
python manage.py migrate
```

#### 服务器环境
```bash
# SSH 登录服务器
cd /path/to/backend
source venv/bin/activate

# 生成迁移文件
python manage.py makemigrations authentication
python manage.py makemigrations pagtive

# 应用迁移
python manage.py migrate
```

### 步骤3：升级现有用户到多账号体系

创建升级脚本 `upgrade_users.py`：

```python
#!/usr/bin/env python
import os
import sys
import django

# 设置 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from authentication.models import User, UserAccount, FeishuAuth
from django.db import transaction

@transaction.atomic
def upgrade_existing_users():
    """升级现有用户到多账号体系"""
    
    print("开始升级用户系统...")
    
    # 1. 迁移飞书用户
    feishu_count = 0
    for feishu_auth in FeishuAuth.objects.all():
        try:
            # 检查是否已存在
            existing = UserAccount.objects.filter(
                user=feishu_auth.user,
                provider='feishu'
            ).first()
            
            if not existing:
                account = UserAccount.objects.create(
                    user=feishu_auth.user,
                    type='oauth',
                    provider='feishu',
                    provider_account_id=feishu_auth.open_id,
                    access_token=feishu_auth.access_token,
                    refresh_token=feishu_auth.refresh_token,
                    expires_at=feishu_auth.token_expires_at,
                    is_primary=True,
                    is_verified=True,
                    provider_profile={
                        'open_id': feishu_auth.open_id,
                        'union_id': feishu_auth.union_id,
                    }
                )
                print(f"✓ 升级飞书用户: {feishu_auth.user.username}")
                feishu_count += 1
        except Exception as e:
            print(f"✗ 升级失败 {feishu_auth.user.username}: {e}")
    
    # 2. 处理邮箱用户（没有飞书账号的）
    email_count = 0
    for user in User.objects.filter(feishu_auth__isnull=True):
        if user.email and not user.accounts.exists():
            try:
                account = UserAccount.objects.create(
                    user=user,
                    type='email',
                    provider='email',
                    provider_account_id=user.email,
                    is_primary=True,
                    is_verified=True,
                )
                print(f"✓ 创建邮箱账号: {user.username}")
                email_count += 1
            except Exception as e:
                print(f"✗ 处理失败 {user.username}: {e}")
    
    # 3. 统计结果
    print("\n" + "="*50)
    print("升级完成统计:")
    print(f"  飞书账号: {feishu_count}")
    print(f"  邮箱账号: {email_count}")
    print(f"  用户总数: {User.objects.count()}")
    print(f"  账号总数: {UserAccount.objects.count()}")
    print("="*50)

if __name__ == '__main__':
    upgrade_existing_users()
```

执行升级：
```bash
# 本地环境
python upgrade_users.py

# 服务器环境
python upgrade_users.py
```

### 步骤4：迁移 pagtive_previews 数据

#### 4.1 安装依赖
```bash
pip install psycopg2-binary
```

#### 4.2 创建迁移脚本 `migrate_pagtive_data.py`

```python
#!/usr/bin/env python
"""
迁移 pagtive_previews 数据库到 Django 系统
"""
import os
import sys
import django
import psycopg2
from datetime import datetime
from django.utils import timezone
import json

# 设置 Django 环境
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from authentication.models import User, UserAccount
from webapps.pagtive.models import Project, ProjectDetail, ProjectLLMLog
from django.db import transaction

class PagtiveMigrator:
    def __init__(self, source_db_config):
        self.source_conn = psycopg2.connect(**source_db_config)
        self.source_cursor = self.source_conn.cursor()
        self.user_mapping = {}
        
    def close(self):
        self.source_cursor.close()
        self.source_conn.close()
    
    @transaction.atomic
    def migrate_users(self):
        """迁移或匹配用户"""
        print("处理用户数据...")
        
        # 查询源数据库用户
        self.source_cursor.execute("""
            SELECT 
                u.id, u.email, u.name, u.username,
                u.status, u.role, u.agreed_agreement_version,
                u.created_at, u.updated_at
            FROM users u
        """)
        
        users = self.source_cursor.fetchall()
        
        for user_data in users:
            (old_id, email, name, username, status, role, 
             agreed_version, created_at, updated_at) = user_data
            
            # 尝试匹配现有用户
            django_user = None
            
            # 1. 先尝试通过邮箱匹配
            if email:
                django_user = User.objects.filter(email=email).first()
            
            # 2. 如果没找到，创建新用户
            if not django_user:
                # 处理时区
                if created_at and timezone.is_naive(created_at):
                    created_at = timezone.make_aware(created_at)
                
                django_user = User.objects.create(
                    username=username or email.split('@')[0] if email else f'user_{old_id[:8]}',
                    email=email,
                    first_name=name or '',
                    is_active=True,
                    date_joined=created_at or timezone.now(),
                    status=status if status is not None else 1,
                    role=role or 'user',
                    agreed_agreement_version=agreed_version,
                )
                
                # 创建邮箱账号
                if email:
                    UserAccount.objects.create(
                        user=django_user,
                        type='email',
                        provider='email',
                        provider_account_id=email,
                        is_primary=True,
                        is_verified=True,
                    )
                
                print(f"  ✓ 创建新用户: {django_user.username}")
            else:
                # 更新现有用户的扩展字段
                if status is not None:
                    django_user.status = status
                if role:
                    django_user.role = role
                if agreed_version:
                    django_user.agreed_agreement_version = agreed_version
                django_user.save()
                print(f"  ✓ 匹配现有用户: {django_user.username}")
            
            # 保存映射关系
            self.user_mapping[old_id] = django_user
        
        print(f"用户处理完成: {len(self.user_mapping)} 个")
    
    def migrate_projects(self):
        """迁移项目数据"""
        print("迁移项目数据...")
        
        self.source_cursor.execute("""
            SELECT id, user_id, project_name, project_description,
                   project_style, global_style_code, pages,
                   is_public, style_tags, batch_id, batch_index,
                   is_featured, is_published, created_at, updated_at
            FROM projects
        """)
        
        projects = self.source_cursor.fetchall()
        migrated = 0
        
        for project_data in projects:
            (id, user_id, name, description, style, global_style,
             pages, is_public, style_tags, batch_id, batch_index,
             is_featured, is_published, created_at, updated_at) = project_data
            
            if user_id not in self.user_mapping:
                print(f"  跳过项目 {name}: 用户未找到")
                continue
            
            django_user = self.user_mapping[user_id]
            
            # 处理时区
            if created_at and timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if updated_at and timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at)
            
            # 创建或更新项目
            project, created = Project.objects.update_or_create(
                id=id,
                defaults={
                    'user': django_user,
                    'project_name': name,
                    'project_description': description,
                    'project_style': style,
                    'global_style_code': global_style,
                    'pages': pages,
                    'is_public': is_public or False,
                    'style_tags': style_tags or [],
                    'batch_id': batch_id,
                    'batch_index': batch_index,
                    'is_featured': is_featured or False,
                    'is_published': is_published or False,
                    'created_at': created_at,
                    'updated_at': updated_at,
                }
            )
            
            if created:
                print(f"  ✓ 创建项目: {name}")
            else:
                print(f"  ✓ 更新项目: {name}")
            migrated += 1
        
        print(f"项目迁移完成: {migrated} 个")
        
    def migrate_project_details(self):
        """迁移项目详情"""
        print("迁移项目详情...")
        
        self.source_cursor.execute("""
            SELECT project_id, page_id, script, styles, html,
                   images, mermaid_content, "versionId",
                   created_at, updated_at
            FROM project_details
        """)
        
        details = self.source_cursor.fetchall()
        migrated = 0
        
        for detail_data in details:
            (project_id, page_id, script, styles, html,
             images, mermaid_content, version_id,
             created_at, updated_at) = detail_data
            
            # 检查项目是否存在
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                continue
            
            # 处理时区
            if created_at and timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if updated_at and timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at)
            
            detail, created = ProjectDetail.objects.update_or_create(
                project=project,
                page_id=page_id,
                defaults={
                    'script': script,
                    'styles': styles,
                    'html': html,
                    'images': images,
                    'mermaid_content': mermaid_content,
                    'version_id': version_id,
                    'created_at': created_at,
                    'updated_at': updated_at,
                }
            )
            
            if created:
                print(f"  ✓ 创建详情: {project.project_name} - Page {page_id}")
            migrated += 1
        
        print(f"项目详情迁移完成: {migrated} 条")
    
    def migrate_all(self):
        """执行完整迁移"""
        print("="*50)
        print("开始数据迁移...")
        print("="*50)
        
        try:
            self.migrate_users()
            self.migrate_projects()
            self.migrate_project_details()
            
            print("\n" + "="*50)
            print("迁移完成！")
            print("="*50)
            self.print_statistics()
        except Exception as e:
            print(f"\n错误: {e}")
            raise
        finally:
            self.close()
    
    def print_statistics(self):
        """输出统计信息"""
        from django.db.models import Count
        
        print("\n统计信息:")
        print(f"  用户总数: {User.objects.count()}")
        print(f"  账号总数: {UserAccount.objects.count()}")
        
        provider_stats = UserAccount.objects.values('provider').annotate(count=Count('id'))
        for stat in provider_stats:
            print(f"    - {stat['provider']}: {stat['count']}")
        
        print(f"  项目总数: {Project.objects.count()}")
        print(f"  项目详情: {ProjectDetail.objects.count()}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='迁移 pagtive_previews 数据')
    parser.add_argument('--host', default='localhost', help='源数据库主机')
    parser.add_argument('--port', default=5432, type=int, help='源数据库端口')
    parser.add_argument('--database', default='pagtive_previews', help='源数据库名')
    parser.add_argument('--user', default='postgres', help='源数据库用户')
    parser.add_argument('--password', default='caijia332335', help='源数据库密码')
    parser.add_argument('--yes', action='store_true', help='跳过确认')
    
    args = parser.parse_args()
    
    # 配置源数据库
    source_db_config = {
        'host': args.host,
        'port': args.port,
        'database': args.database,
        'user': args.user,
        'password': args.password,
    }
    
    if not args.yes:
        print("数据迁移配置:")
        print(f"  源数据库: {source_db_config['host']}:{source_db_config['port']}/{source_db_config['database']}")
        print(f"  目标数据库: Django 配置的数据库")
        print("\n⚠️  警告：此操作将迁移数据到 Django 数据库")
        
        response = input("确认开始迁移？(yes/no): ")
        if response.lower() != 'yes':
            print("迁移已取消")
            return
    
    # 执行迁移
    migrator = PagtiveMigrator(source_db_config)
    migrator.migrate_all()

if __name__ == '__main__':
    main()
```

#### 4.3 执行数据迁移

##### 本地环境
```bash
# 交互式确认
python migrate_pagtive_data.py

# 跳过确认
python migrate_pagtive_data.py --yes

# 自定义数据库参数
python migrate_pagtive_data.py --host localhost --database pagtive_previews --password caijia332335
```

##### 服务器环境
```bash
# SSH 登录服务器后
cd /path/to/backend
source venv/bin/activate

# 如果源数据库在同一服务器
python migrate_pagtive_data.py --yes

# 如果源数据库在其他服务器
python migrate_pagtive_data.py --host source_db_host --password source_db_password
```

## 三、验证步骤

### 验证用户升级
```python
python manage.py shell
```

```python
from authentication.models import User, UserAccount
from django.db.models import Count

# 检查账号分布
stats = UserAccount.objects.values('provider').annotate(count=Count('id'))
for stat in stats:
    print(f"{stat['provider']}: {stat['count']}")

# 检查用户账号关联
for user in User.objects.all()[:5]:
    accounts = user.accounts.all()
    print(f"\n{user.username}:")
    for acc in accounts:
        print(f"  - {acc.provider} {'(主账号)' if acc.is_primary else ''}")
```

### 验证数据迁移
```python
from pagtive.models import Project, ProjectDetail

# 检查项目
projects = Project.objects.all()
print(f"项目总数: {projects.count()}")

# 检查项目用户关联
for project in projects[:5]:
    print(f"{project.project_name} - 用户: {project.user.username}")

# 检查项目详情
details = ProjectDetail.objects.all()
print(f"项目详情总数: {details.count()}")
```

## 四、注意事项

### 用户匹配策略
1. **优先通过邮箱匹配**：源数据库用户邮箱 → Django 用户邮箱
2. **新用户自动创建**：如果没有匹配到，创建新用户并添加邮箱账号
3. **重复邮箱处理**：脚本会自动跳过重复邮箱的用户

### 数据完整性
1. **用户 ID 映射**：源数据库 UUID → Django 整数 ID
2. **项目 ID 保持**：项目使用原始 UUID 作为主键
3. **时区处理**：自动转换 naive datetime 为 aware datetime

### 服务器特殊注意
1. **宝塔数据库访问**：
   - 可通过宝塔面板 phpMyAdmin 查看数据
   - 或 SSH 后使用 psql 命令
2. **权限问题**：确保有足够权限创建表和插入数据
3. **防火墙**：如果跨服务器迁移，注意防火墙端口开放

## 五、回滚方案

如果需要回滚：

```bash
# 1. 回滚 pagtive 迁移
python manage.py migrate pagtive zero

# 2. 回滚 authentication 迁移到原始状态
python manage.py migrate authentication 0004

# 3. 从备份恢复数据库
# 本地
psql -U postgres -d X < backup_X_20250120_xxxx.sql

# 服务器
sudo -u postgres psql X < /backup/backup_X_20250120_xxxx.sql
```

## 六、常见问题

### Q1: 字段已存在错误
A: 说明之前已经部分迁移，可以：
1. 检查已有字段：`\d authentication_user` (在 psql 中)
2. 手动编辑迁移文件，跳过已存在的字段
3. 或使用 `--fake` 标记跳过：`python manage.py migrate authentication 0005 --fake`

### Q2: 用户重复错误
A: 邮箱重复时会跳过创建，检查日志确认哪些用户被跳过

### Q3: 外键约束错误
A: 确保按顺序迁移：先用户 → 再项目 → 最后详情

### Q4: 时区错误
A: 脚本会自动处理，如果仍有问题，检查 Django 设置：
```python
# settings.py
USE_TZ = True
TIME_ZONE = 'Asia/Shanghai'
```

## 七、执行清单

- [ ] 备份所有数据库
- [ ] 在测试环境验证流程
- [ ] 执行数据库结构迁移
- [ ] 升级现有用户到多账号体系
- [ ] 迁移 pagtive_previews 数据
- [ ] 验证迁移结果
- [ ] 更新生产环境配置
- [ ] 监控系统运行状态