"""
用户相关工具函数
"""

import os
import logging
from django.contrib.auth import get_user_model
from authentication.models import UserAccount
from authentication.models_extension import UserProfile
from authentication.user_service import UserService as LegacyUserService

logger = logging.getLogger(__name__)
User = get_user_model()


class UserProfileManager:
    """用户配置文件管理器"""
    
    @staticmethod
    def ensure_user_profile(user):
        """
        确保用户有UserProfile
        
        Args:
            user: 用户对象
            
        Returns:
            tuple: (profile, created)
        """
        try:
            # 判断用户类型
            is_feishu = UserAccount.objects.filter(user=user, provider='feishu').exists()
            
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'subscription_type': (
                        UserProfile.SubscriptionType.ENTERPRISE 
                        if is_feishu 
                        else UserProfile.SubscriptionType.FREE
                    )
                }
            )
            
            if created:
                # 应用配额模板
                template_name = 'enterprise_user' if is_feishu else 'free_user'
                try:
                    LegacyUserService.apply_quota_template(user.id, template_name)
                    logger.info(f"为用户 {user.username} 创建UserProfile并应用{template_name}配额")
                except Exception as e:
                    logger.error(f"为用户 {user.username} 应用配额模板失败: {e}")
            
            return profile, created
            
        except Exception as e:
            logger.error(f"创建UserProfile失败: {e}", exc_info=True)
            return None, False
    
    @staticmethod
    def determine_user_status(provider):
        """
        根据提供商和配置确定用户状态
        
        Args:
            provider: 认证提供商
            
        Returns:
            int: 用户状态
        """
        require_activation = os.getenv('REQUIRE_USER_ACTIVATION', 'False').lower() == 'true'
        
        # 飞书用户始终默认激活（企业用户）
        if provider == 'feishu':
            return User.Status.ACTIVE
        
        # 其他提供商根据配置决定
        # 如果需要激活，则用户默认未激活
        if require_activation:
            return User.Status.INACTIVE
        
        return User.Status.ACTIVE
    
    @staticmethod
    def create_user_account(user, provider, provider_account_id, account_type, **kwargs):
        """
        创建用户账号关联
        
        Args:
            user: 用户对象
            provider: 提供商
            provider_account_id: 提供商账号ID
            account_type: 账号类型
            **kwargs: 其他参数
            
        Returns:
            UserAccount: 创建的账号对象
        """
        # 检查是否是第一个账号
        is_first_account = user.accounts.count() == 0
        
        account = UserAccount.objects.create(
            user=user,
            type=account_type,
            provider=provider,
            provider_account_id=provider_account_id,
            is_primary=is_first_account,  # 第一个账号设为主账号
            **kwargs
        )
        
        logger.info(f"为用户 {user.username} 创建{provider}账号关联")
        return account
    
    @staticmethod
    def update_account_tokens(account, tokens):
        """
        更新账号令牌
        
        Args:
            account: UserAccount对象
            tokens: 令牌信息字典
        """
        from django.utils import timezone
        
        account.access_token = tokens.get('access_token')
        account.refresh_token = tokens.get('refresh_token')
        account.expires_at = tokens.get('expires_at')
        account.last_used_at = timezone.now()
        account.save()
        
        logger.info(f"更新账号令牌: user={account.user.username}, provider={account.provider}")
    
    @staticmethod
    def generate_unique_username(base_username):
        """
        生成唯一的用户名
        
        Args:
            base_username: 基础用户名
            
        Returns:
            str: 唯一的用户名
        """
        username = base_username
        counter = 1
        
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        return username