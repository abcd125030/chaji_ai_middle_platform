"""
多账号认证核心服务
"""

import logging
from django.db import transaction
from django.contrib.auth import get_user_model
from authentication.models import UserAccount
from .utils.user_utils import UserProfileManager
from .utils.token_utils import TokenManager

logger = logging.getLogger(__name__)
User = get_user_model()


class MultiAuthService:
    """多账号认证服务 - 核心服务类"""
    
    @staticmethod
    @transaction.atomic
    def create_or_login_oauth_user(provider, provider_account_id, profile_data, tokens):
        """
        OAuth用户创建或登录
        
        Args:
            provider: 提供商（'feishu', 'google', 'github'等）
            provider_account_id: 提供商的用户ID
            profile_data: 用户信息（包含 email, name, avatar等）
            tokens: OAuth令牌信息
        
        Returns:
            tuple: (user, account, created) - 用户对象、账号对象、是否新创建
        """
        # 1. 尝试通过提供商账号ID查找已存在的账号
        account = UserAccount.objects.filter(
            provider=provider,
            provider_account_id=provider_account_id
        ).first()
        
        if account:
            # 已存在账号，更新令牌
            UserProfileManager.update_account_tokens(account, tokens)
            return account.user, account, False
        
        # 2. 尝试通过邮箱查找已存在的用户
        email = profile_data.get('email')
        user = None
        
        if email:
            user = User.objects.filter(email=email).first()
        
        # 3. 如果没有找到用户，创建新用户
        if not user:
            user = MultiAuthService._create_oauth_user(provider, provider_account_id, profile_data)
        
        # 4. 创建新的账号关联
        account = MultiAuthService._create_oauth_account(user, provider, provider_account_id, profile_data, tokens)
        
        return user, account, True
    
    @staticmethod
    def _create_oauth_user(provider, provider_account_id, profile_data):
        """
        创建OAuth用户
        
        Args:
            provider: 提供商
            provider_account_id: 提供商账号ID
            profile_data: 用户信息
            
        Returns:
            User: 创建的用户对象
        """
        email = profile_data.get('email')
        username_base = profile_data.get('name', email.split('@')[0] if email else f'user_{provider_account_id}')
        username = UserProfileManager.generate_unique_username(username_base)
        
        user = User.objects.create(
            username=username,
            email=email,
            first_name=profile_data.get('first_name', ''),
            last_name=profile_data.get('last_name', ''),
            avatar_url=profile_data.get('avatar_url'),
        )
        
        # 设置用户状态
        user.status = UserProfileManager.determine_user_status(provider)
        user.save()
        
        status_text = "激活" if user.status == User.Status.ACTIVE else "未激活"
        logger.info(f"{provider.capitalize()}用户 {user.email} 创建成功，状态设为{status_text}({user.status})")
        
        # 创建UserProfile
        UserProfileManager.ensure_user_profile(user)
        
        return user
    
    @staticmethod
    def _create_oauth_account(user, provider, provider_account_id, profile_data, tokens):
        """
        创建OAuth账号关联
        
        Args:
            user: 用户对象
            provider: 提供商
            provider_account_id: 提供商账号ID
            profile_data: 用户信息
            tokens: 令牌信息
            
        Returns:
            UserAccount: 创建的账号对象
        """
        from datetime import timedelta
        from django.utils import timezone
        
        # 计算令牌过期时间
        expires_at = None
        if tokens.get('expires_in'):
            expires_at = timezone.now() + timedelta(seconds=tokens['expires_in'])
        
        account = UserProfileManager.create_user_account(
            user=user,
            provider=provider,
            provider_account_id=provider_account_id,
            account_type=UserAccount.AccountType.OAUTH,
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            expires_at=expires_at,
            scope=tokens.get('scope'),
            id_token=tokens.get('id_token'),
            is_verified=True,
            provider_profile=profile_data,
            nickname=profile_data.get('nickname'),
            avatar_url=profile_data.get('avatar_url'),
            last_used_at=timezone.now()
        )
        
        return account
    
    @staticmethod
    def bind_oauth_account(user, provider, provider_account_id, profile_data, tokens):
        """
        为已存在用户绑定OAuth账号
        
        Args:
            user: 用户对象
            provider: 提供商
            provider_account_id: 提供商账号ID
            profile_data: 用户信息
            tokens: 令牌信息
            
        Returns:
            UserAccount: 创建的账号对象，如果已存在则返回None
        """
        # 检查是否已绑定
        if UserAccount.objects.filter(user=user, provider=provider).exists():
            logger.warning(f"用户 {user.username} 已绑定 {provider} 账号")
            return None
        
        # 检查提供商账号是否已被其他用户使用
        existing = UserAccount.objects.filter(
            provider=provider,
            provider_account_id=provider_account_id
        ).first()
        
        if existing:
            logger.warning(f"{provider} 账号 {provider_account_id} 已被用户 {existing.user.username} 绑定")
            return None
        
        # 创建绑定
        account = MultiAuthService._create_oauth_account(user, provider, provider_account_id, profile_data, tokens)
        logger.info(f"用户 {user.username} 成功绑定 {provider} 账号")
        
        return account
    
    @staticmethod
    def unbind_oauth_account(user, provider):
        """
        解绑OAuth账号
        
        Args:
            user: 用户对象
            provider: 提供商
            
        Returns:
            bool: 是否成功解绑
        """
        # 检查是否可以解绑（至少保留一种登录方式）
        if user.accounts.count() <= 1:
            logger.warning(f"用户 {user.username} 只有一种登录方式，无法解绑")
            return False
        
        account = UserAccount.objects.filter(user=user, provider=provider).first()
        if not account:
            logger.warning(f"用户 {user.username} 未绑定 {provider} 账号")
            return False
        
        # 如果是主账号，需要重新指定主账号
        if account.is_primary:
            other_account = user.accounts.exclude(id=account.id).first()
            if other_account:
                other_account.is_primary = True
                other_account.save()
        
        account.delete()
        logger.info(f"用户 {user.username} 成功解绑 {provider} 账号")
        
        return True