"""
为现有用户创建UserProfile的管理命令
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from authentication.models_extension import UserProfile
from authentication.models import FeishuAuth
from authentication.user_service import UserService
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = '为所有现有用户创建UserProfile（如果不存在）'

    def handle(self, *args, **options):
        users_without_profile = []
        users_with_profile = []
        profiles_created = []
        errors = []
        
        # 获取所有用户
        all_users = User.objects.all()
        total_users = all_users.count()
        
        self.stdout.write(f"开始处理 {total_users} 个用户...")
        
        for user in all_users:
            try:
                # 检查用户是否已有profile
                if hasattr(user, 'profile'):
                    users_with_profile.append(user.username)
                    self.stdout.write(f"✓ 用户 {user.username} 已有UserProfile")
                else:
                    users_without_profile.append(user.username)
                    
                    # 判断用户类型
                    subscription_type = UserProfile.SubscriptionType.FREE
                    
                    # 检查是否为飞书用户
                    if user.auth_type == User.AuthType.FEISHU or FeishuAuth.objects.filter(user=user).exists():
                        subscription_type = UserProfile.SubscriptionType.ENTERPRISE
                        self.stdout.write(f"  检测到飞书用户 {user.username}，设置为企业订阅")
                    
                    # 创建UserProfile
                    profile = UserProfile.objects.create(
                        user=user,
                        subscription_type=subscription_type
                    )
                    
                    profiles_created.append(user.username)
                    self.stdout.write(self.style.SUCCESS(f"✓ 为用户 {user.username} 创建了UserProfile (订阅类型: {subscription_type})"))
                    
                    # 如果是飞书用户，应用enterprise_user配额模板
                    if subscription_type == UserProfile.SubscriptionType.ENTERPRISE:
                        try:
                            UserService.apply_quota_template(user.id, 'enterprise_user')
                            self.stdout.write(f"  ✓ 为飞书用户 {user.username} 应用了企业用户配额模板")
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"  ⚠ 为用户 {user.username} 应用配额模板失败: {e}"))
                    
            except Exception as e:
                errors.append(f"{user.username}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"✗ 处理用户 {user.username} 时出错: {e}"))
                logger.error(f"为用户 {user.username} 创建UserProfile失败", exc_info=True)
        
        # 输出统计信息
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(f"\n处理完成！"))
        self.stdout.write(f"总用户数: {total_users}")
        self.stdout.write(f"已有Profile的用户数: {len(users_with_profile)}")
        self.stdout.write(f"新创建Profile的用户数: {len(profiles_created)}")
        self.stdout.write(f"处理出错的用户数: {len(errors)}")
        
        if profiles_created:
            self.stdout.write(self.style.SUCCESS(f"\n新创建Profile的用户:"))
            for username in profiles_created:
                self.stdout.write(f"  - {username}")
        
        if errors:
            self.stdout.write(self.style.ERROR(f"\n处理出错的用户:"))
            for error in errors:
                self.stdout.write(f"  - {error}")
        
        # 验证结果
        self.stdout.write("\n" + "="*50)
        self.stdout.write("\n验证结果:")
        users_without_profile_after = User.objects.filter(profile__isnull=True).count()
        if users_without_profile_after == 0:
            self.stdout.write(self.style.SUCCESS("✓ 所有用户都有UserProfile了！"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠ 仍有 {users_without_profile_after} 个用户没有UserProfile"))