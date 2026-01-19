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
# 脚本在 backend/_SERVER_ACTIONS/ 目录
# 需要将 backend 目录加入到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)  # 这就是 backend 目录
sys.path.insert(0, backend_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from authentication.models import User, UserAccount, FeishuAuth
from authentication.models_extension import UserProfile
from webapps.pagtive.models import Project, ProjectDetail, ProjectLLMLog, InvitationCode
from django.db import transaction

class PagtiveMigrator:
    def __init__(self, source_db_config, limit_users=None):
        self.source_conn = psycopg2.connect(**source_db_config)
        self.source_cursor = self.source_conn.cursor()
        self.user_mapping = {}
        self.limit_users = limit_users  # 限制迁移的用户数量
        # 统计本次迁移的数据
        self.migrated_users = []
        self.migrated_projects = []
        self.migrated_details = 0
        
    def close(self):
        self.source_cursor.close()
        self.source_conn.close()
    
    @transaction.atomic
    def migrate_user_with_projects(self):
        """逐个用户迁移，包含其项目和项目详情"""
        print("开始逐用户迁移...")
        
        # 查询源数据库用户 - 增加LIMIT限制
        limit_clause = f"LIMIT {self.limit_users}" if self.limit_users else ""
        self.source_cursor.execute(f"""
            SELECT 
                u.id, u.email, u.name, u.username,
                u.status, u.role, u.agreed_agreement_version,
                u.created_at, u.updated_at, u.email_verified,
                u.image, u.last_login, u.twitter_url
            FROM users u
            ORDER BY u.created_at
            {limit_clause}
        """)
        
        users = self.source_cursor.fetchall()
        print(f"将迁移 {len(users)} 个用户")
        
        for idx, user_data in enumerate(users, 1):
            (old_id, email, name, username, status, role, 
             agreed_version, created_at, updated_at, email_verified,
             image, last_login, twitter_url) = user_data
            
            print(f"\n[{idx}/{len(users)}] 处理用户: {name or email}")
            
            # 判断是否是飞书用户
            is_feishu = email and '@feishu.example.com' in email
            
            # 尝试匹配现有用户
            django_user = None
            
            # 1. 通过external_id匹配飞书用户
            if is_feishu and username:
                django_user = User.objects.filter(external_id=username).first()
            
            # 2. 如果没找到，通过邮箱匹配
            if not django_user and email:
                django_user = User.objects.filter(email=email).first()
            
            # 3. 如果没找到，创建新用户
            if not django_user:
                # 处理时区
                if created_at and timezone.is_naive(created_at):
                    created_at = timezone.make_aware(created_at)
                if last_login and timezone.is_naive(last_login):
                    last_login = timezone.make_aware(last_login)
                
                # 设置用户名：飞书用户使用真实姓名，其他用户使用邮箱前缀
                if is_feishu:
                    display_username = name or username or email.split('@')[0]
                    auth_type = 'feishu'
                    external_id = username  # ou_xxx
                else:
                    display_username = email.split('@')[0] if email else f'user_{old_id[:8]}'
                    auth_type = 'email'
                    external_id = None
                
                django_user = User.objects.create(
                    username=display_username,
                    email=email,
                    first_name=name or '',
                    is_active=True,
                    date_joined=created_at or timezone.now(),
                    last_login=last_login,
                    status=status if status is not None else 1,
                    role='user' if role in ['user', 'verified'] else (role or 'user'),  # verified映射为user
                    agreed_agreement_version=agreed_version,
                    auth_type=auth_type,
                    external_id=external_id,
                    avatar_url=image,
                    twitter_url=twitter_url,
                )
                
                # 如果是飞书用户，设置不可用密码
                if is_feishu:
                    django_user.set_unusable_password()
                    django_user.save()
                
                # 创建UserAccount记录（新架构）
                UserAccount.objects.create(
                    user=django_user,
                    type='oauth' if is_feishu else 'email',
                    provider='feishu' if is_feishu else 'email',
                    provider_account_id=username if is_feishu else email,
                    is_primary=True,
                    is_verified=True if email_verified else False,
                    avatar_url=image,
                    provider_profile={
                        'name': name,
                        'email': email,
                        'username': username,
                        'image': image,
                    } if is_feishu else None,
                )
                
                # 如果是飞书用户，创建FeishuAuth记录（兼容旧版）
                # 注意：不迁移令牌，因为它们已过期，用户需要重新登录
                if is_feishu and username:
                    FeishuAuth.objects.create(
                        user=django_user,
                        open_id=username,  # ou_xxx
                        union_id=None,  # 暂时没有union_id数据
                        access_token='',  # 空令牌，需要重新登录
                        refresh_token='',  # 空令牌，需要重新登录
                        token_expires_at=timezone.now(),  # 标记为已过期
                    )
                    print(f"      注意：飞书令牌已过期，用户需要重新登录")
                
                # 创建UserProfile记录
                UserProfile.objects.get_or_create(
                    user=django_user,
                    defaults={
                        'subscription_type': 'enterprise_user' if is_feishu else 'free_user',
                        'industry': 'technology',  # 默认行业
                        'quotas': {},  # 后续会通过信号或其他逻辑自动填充
                        'usage_stats': {},
                        'capabilities': [],
                        'preferences': {},
                        'context_data': {},
                    }
                )
                
                print(f"  ✓ 创建新用户: {django_user.username} ({'飞书' if is_feishu else '邮箱'}用户)")
                self.migrated_users.append(django_user)
            else:
                # 更新现有用户的扩展字段
                updated_fields = []
                
                if status is not None and django_user.status != status:
                    django_user.status = status
                    updated_fields.append('status')
                    
                # 处理role字段，verified映射为user
                mapped_role = 'user' if role in ['user', 'verified'] else (role or 'user')
                if mapped_role and django_user.role != mapped_role:
                    django_user.role = mapped_role
                    updated_fields.append('role')
                    
                if agreed_version and django_user.agreed_agreement_version != agreed_version:
                    django_user.agreed_agreement_version = agreed_version
                    updated_fields.append('agreed_agreement_version')
                    
                if image and not django_user.avatar_url:
                    django_user.avatar_url = image
                    updated_fields.append('avatar_url')
                    
                if twitter_url and not django_user.twitter_url:
                    django_user.twitter_url = twitter_url
                    updated_fields.append('twitter_url')
                    
                if last_login and timezone.is_naive(last_login):
                    last_login = timezone.make_aware(last_login)
                if last_login and (not django_user.last_login or django_user.last_login < last_login):
                    django_user.last_login = last_login
                    updated_fields.append('last_login')
                
                if updated_fields:
                    django_user.save()
                    print(f"  ✓ 更新现有用户: {django_user.username} (更新字段: {', '.join(updated_fields)})")
                else:
                    print(f"  ✓ 匹配现有用户: {django_user.username} (无需更新)")
                
                # 记录为本次迁移的用户（即使是更新）
                self.migrated_users.append(django_user)
                
                # 确保UserAccount存在（对于已存在的用户）
                if is_feishu:
                    account, created = UserAccount.objects.get_or_create(
                        user=django_user,
                        provider='feishu',
                        defaults={
                            'type': 'oauth',
                            'provider_account_id': username,
                            'is_primary': True,
                            'is_verified': True if email_verified else False,
                            'avatar_url': image,
                            'provider_profile': {
                                'name': name,
                                'email': email,
                                'username': username,
                                'image': image,
                            },
                        }
                    )
                    if created:
                        print(f"    创建UserAccount")
                    else:
                        # 更新已存在的UserAccount
                        if account.provider_account_id != username:
                            account.provider_account_id = username
                            account.save()
                            print(f"    更新UserAccount")
                
                # 确保FeishuAuth存在（对于已存在的飞书用户）
                if is_feishu and username:
                    if not FeishuAuth.objects.filter(user=django_user).exists():
                        FeishuAuth.objects.create(
                            user=django_user,
                            open_id=username,
                            union_id=None,
                            access_token='',
                            refresh_token='',
                            token_expires_at=timezone.now(),
                        )
                        print(f"    创建FeishuAuth")
                
                # 确保UserProfile存在
                UserProfile.objects.get_or_create(
                    user=django_user,
                    defaults={
                        'subscription_type': 'enterprise_user' if is_feishu else 'free_user',
                        'industry': 'technology',
                        'quotas': {},
                        'usage_stats': {},
                        'capabilities': [],
                        'preferences': {},
                        'context_data': {},
                    }
                )
            
            # 保存映射关系
            self.user_mapping[old_id] = django_user
            
            # 立即迁移该用户的项目和详情
            self.migrate_user_projects(old_id, django_user)
        
        print(f"\n用户及其项目迁移完成: {len(self.user_mapping)} 个用户")
    
    def migrate_user_projects(self, user_id, django_user):
        """迁移特定用户的所有项目和项目详情"""
        # 查询该用户的所有项目
        self.source_cursor.execute("""
            SELECT id, user_id, project_name, project_description,
                   project_style, global_style_code, pages,
                   is_public, style_tags, batch_id, batch_index,
                   is_featured, is_published, created_at, updated_at
            FROM projects
            WHERE user_id = %s
        """, (user_id,))
        
        projects = self.source_cursor.fetchall()
        
        if not projects:
            print(f"    该用户没有项目")
            return
        
        print(f"    找到 {len(projects)} 个项目")
        
        for project_data in projects:
            (project_id, user_id, name, description, style, global_style,
             pages, is_public, style_tags, batch_id, batch_index,
             is_featured, is_published, created_at, updated_at) = project_data
            
            # 处理时区
            if created_at and timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if updated_at and timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at)
            
            # 创建或更新项目
            project, created = Project.objects.update_or_create(
                id=project_id,
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
            
            action = "创建" if created else "更新"
            print(f"      ✓ {action}项目: {name[:30]}...")
            # 无论创建还是更新，都记录为本次迁移的项目
            self.migrated_projects.append(project)
            
            # 立即迁移该项目的详情
            self.migrate_project_details(project_id, project)
        
    def migrate_project_details(self, project_id, project):
        """迁移特定项目的详情"""
        self.source_cursor.execute("""
            SELECT project_id, page_id, script, styles, html,
                   images, mermaid_content, "versionId",
                   created_at, updated_at
            FROM project_details
            WHERE project_id = %s
        """, (project_id,))
        
        details = self.source_cursor.fetchall()
        
        if not details:
            return
        
        for detail_data in details:
            (_, page_id, script, styles, html,
             images, mermaid_content, version_id,
             created_at, updated_at) = detail_data
            
            # 处理时区
            if created_at and timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if updated_at and timezone.is_naive(updated_at):
                updated_at = timezone.make_aware(updated_at)
            
            # 处理page_id的类型 - 确保是整数
            try:
                if isinstance(page_id, str):
                    page_id_int = int(page_id)
                else:
                    page_id_int = page_id
            except (ValueError, TypeError):
                print(f"        ⚠ 跳过详情: 无效的page_id '{page_id}'")
                continue
            
            detail, created = ProjectDetail.objects.update_or_create(
                project=project,
                page_id=page_id_int,
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
            
            action = "创建" if created else "更新"
            print(f"        ✓ {action}详情: Page {page_id_int}")
            # 无论创建还是更新，都记录为本次迁移的详情
            self.migrated_details += 1
    
    # 移除LLM日志迁移（不再需要）
    # def migrate_llmlog(self):
        
        self.source_cursor.execute("""
            SELECT id, user_id, project_id, page_id,
                   provider, model, scenario,
                   request_timestamp, request_prompts, request_config,
                   response_timestamp, response_content, response_error,
                   usage_prompt_tokens, usage_completion_tokens, usage_total_tokens,
                   duration_ms, status, temporary_page_id
            FROM llmlog
        """)
        
        logs = self.source_cursor.fetchall()
        migrated = 0
        skipped = 0
        
        for log_data in logs:
            (id, user_id, project_id, page_id,
             provider, model, scenario,
             request_timestamp, request_prompts, request_config,
             response_timestamp, response_content, response_error,
             usage_prompt_tokens, usage_completion_tokens, usage_total_tokens,
             duration_ms, status, temporary_page_id) = log_data
            
            # 检查用户映射
            if user_id and user_id not in self.user_mapping:
                print(f"  跳过日志 {id[:8]}: 用户未找到")
                skipped += 1
                continue
            
            # 检查项目是否存在（可选的外键）
            project = None
            if project_id:
                try:
                    project = Project.objects.get(id=project_id)
                except Project.DoesNotExist:
                    print(f"  跳过日志 {id[:8]}: 项目 {project_id[:8]} 未找到")
                    skipped += 1
                    continue
            
            django_user = self.user_mapping[user_id] if user_id else None
            
            # 处理时区
            if request_timestamp and timezone.is_naive(request_timestamp):
                request_timestamp = timezone.make_aware(request_timestamp)
            if response_timestamp and timezone.is_naive(response_timestamp):
                response_timestamp = timezone.make_aware(response_timestamp)
            
            try:
                log, created = ProjectLLMLog.objects.update_or_create(
                    id=id,
                    defaults={
                        'user': django_user,
                        'project': project,
                        'page_id': page_id,
                        'provider': provider,
                        'model': model,
                        'scenario': scenario,
                        'request_timestamp': request_timestamp,
                        'request_prompts': request_prompts,
                        'request_config': request_config,
                        'response_timestamp': response_timestamp,
                        'response_content': response_content,
                        'response_error': response_error,
                        'usage_prompt_tokens': usage_prompt_tokens,
                        'usage_completion_tokens': usage_completion_tokens,
                        'usage_total_tokens': usage_total_tokens,
                        'duration_ms': duration_ms,
                        'status': status,
                        'temporary_page_id': temporary_page_id,
                    }
                )
                
                if created:
                    print(f"  ✓ 创建LLM日志: {model} - {scenario}")
                else:
                    print(f"  ✓ 更新LLM日志: {model} - {scenario}")
                migrated += 1
                
            except Exception as e:
                print(f"  ✗ 迁移日志 {id[:8]} 失败: {e}")
                skipped += 1
        
        print(f"LLM日志迁移完成: {migrated} 条成功, {skipped} 条跳过")
    
    # 移除邀请码迁移（不再需要）
    # def migrate_invitation_codes(self):
        
        self.source_cursor.execute("""
            SELECT id, code, status, created_at, expires_at,
                   used_at, used_by_user_id
            FROM invitation_codes
        """)
        
        codes = self.source_cursor.fetchall()
        
        if not codes:
            print("  没有邀请码数据需要迁移")
            return
        
        migrated = 0
        
        for code_data in codes:
            (id, code, status, created_at, expires_at,
             used_at, used_by_user_id) = code_data
            
            # 处理使用者
            used_by = None
            if used_by_user_id and used_by_user_id in self.user_mapping:
                used_by = self.user_mapping[used_by_user_id]
            
            # 处理时区
            if created_at and timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if expires_at and timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
            if used_at and timezone.is_naive(used_at):
                used_at = timezone.make_aware(used_at)
            
            try:
                invitation, created = InvitationCode.objects.update_or_create(
                    id=id,
                    defaults={
                        'code': code,
                        'status': status,
                        'created_at': created_at,
                        'expires_at': expires_at,
                        'used_at': used_at,
                        'used_by_user': used_by,
                    }
                )
                
                if created:
                    print(f"  ✓ 创建邀请码: {code}")
                migrated += 1
                
            except Exception as e:
                print(f"  ✗ 迁移邀请码 {code} 失败: {e}")
        
        print(f"邀请码迁移完成: {migrated} 条")
    
    def migrate_all(self):
        """执行逐用户迁移"""
        print("="*50)
        print(f"开始数据迁移...{f'(限制{self.limit_users}个用户)' if self.limit_users else ''}")
        print("="*50)
        
        try:
            # 只执行逐用户迁移
            self.migrate_user_with_projects()
            
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
        """输出本次迁移统计信息"""
        print("\n本次迁移统计:")
        print(f"  迁移用户数: {len(self.migrated_users)}")
        if self.migrated_users:
            for user in self.migrated_users:
                print(f"    - {user.username} ({user.email})")
        
        print(f"  迁移项目数: {len(self.migrated_projects)}")
        print(f"  迁移项目详情数: {self.migrated_details}")
        
        # 显示数据库总体统计
        print("\n数据库总体统计:")
        print(f"  用户总数: {User.objects.count()}")
        print(f"  项目总数: {Project.objects.count()}")
        print(f"  项目详情总数: {ProjectDetail.objects.count()}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='迁移 pagtive_previews 数据')
    parser.add_argument('--host', default='localhost', help='源数据库主机')
    parser.add_argument('--port', default=5432, type=int, help='源数据库端口')
    parser.add_argument('--database', default='pagtive_preview', help='源数据库名')
    parser.add_argument('--user', default='postgres', help='源数据库用户')
    parser.add_argument('--password', default='caijia332335', help='源数据库密码')
    parser.add_argument('--limit', type=int, help='限制迁移的用户数量（用于测试）')
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
        if args.limit:
            print(f"  限制用户数: {args.limit}")
        print("\n⚠️  警告：此操作将迁移数据到 Django 数据库")
        
        response = input("确认开始迁移？(yes/no): ")
        if response.lower() != 'yes':
            print("迁移已取消")
            return
    
    # 执行迁移
    migrator = PagtiveMigrator(source_db_config, limit_users=args.limit)
    migrator.migrate_all()

if __name__ == '__main__':
    main()