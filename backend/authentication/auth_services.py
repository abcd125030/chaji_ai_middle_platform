"""
多账号认证服务示例
展示如何使用新的 UserAccount 模型处理不同的登录方式
"""

from django.contrib.auth import authenticate, login
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import secrets
import hashlib
import logging

from .models import User, UserAccount, EmailVerification, OAuthState

logger = logging.getLogger(__name__)


class MultiAuthService:
    """多账号认证服务"""
    
    @staticmethod
    @transaction.atomic
    def create_or_login_oauth_user(provider, provider_account_id, profile_data, tokens):
        """
        OAuth 用户创建或登录
        
        Args:
            provider: 提供商（'feishu', 'google', 'github'等）
            provider_account_id: 提供商的用户ID
            profile_data: 用户信息（包含 email, name, avatar等）
            tokens: OAuth令牌信息
        
        Returns:
            (user, account, created): 用户对象、账号对象、是否新创建
        """
        
        # 1. 尝试通过提供商账号ID查找已存在的账号
        account = UserAccount.objects.filter(
            provider=provider,
            provider_account_id=provider_account_id
        ).first()
        
        if account:
            # 已存在账号，更新令牌
            account.access_token = tokens.get('access_token')
            account.refresh_token = tokens.get('refresh_token')
            account.expires_at = tokens.get('expires_at')
            account.last_used_at = timezone.now()
            account.save()
            
            return account.user, account, False
        
        # 2. 尝试通过邮箱查找已存在的用户
        email = profile_data.get('email')
        user = None
        
        if email:
            user = User.objects.filter(email=email).first()
        
        # 3. 如果没有找到用户，创建新用户
        if not user:
            import os
            
            user = User.objects.create(
                username=profile_data.get('name', email.split('@')[0] if email else f'user_{provider_account_id}'),
                email=email,
                first_name=profile_data.get('first_name', ''),
                last_name=profile_data.get('last_name', ''),
                avatar_url=profile_data.get('avatar_url'),
            )
            
            # 检查是否需要用户激活
            require_activation = os.getenv('REQUIRE_USER_ACTIVATION', 'False').lower() == 'true'
            
            # 飞书用户始终默认激活（企业用户）
            if provider == 'feishu':
                user.status = User.Status.ACTIVE
                logger.info(f"飞书用户 {user.email} 创建成功，状态设为激活(ACTIVE)")
            elif require_activation:
                # Google等其他OAuth用户根据配置决定是否需要激活
                user.status = User.Status.INACTIVE
                logger.info(f"{provider.capitalize()}用户 {user.email} 创建成功，状态设为未激活(INACTIVE)")
            else:
                user.status = User.Status.ACTIVE
                logger.info(f"{provider.capitalize()}用户 {user.email} 创建成功，状态设为激活(ACTIVE)")
            
            user.save()
            
            # 为新用户创建 UserProfile
            try:
                from .models_extension import UserProfile
                profile = UserProfile.objects.create(user=user)
                logger.info(f"为新用户 {user.username} 创建 UserProfile")
            except Exception as e:
                logger.error(f"为新用户 {user.username} 创建 UserProfile 失败: {e}")
        
        # 4. 创建新的账号关联
        account = UserAccount.objects.create(
            user=user,
            type=UserAccount.AccountType.OAUTH,
            provider=provider,
            provider_account_id=provider_account_id,
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            expires_at=tokens.get('expires_at'),
            scope=tokens.get('scope'),
            id_token=tokens.get('id_token'),
            is_verified=True,
            provider_profile=profile_data,
            nickname=profile_data.get('nickname'),
            avatar_url=profile_data.get('avatar_url'),
        )
        
        # 5. 如果用户没有其他账号，设为主账号
        if user.accounts.count() == 1:
            account.is_primary = True
            account.save()
        
        # 6. 确保所有用户都有 UserProfile，并根据提供商设置订阅类型
        try:
            from .user_service import UserService
            from .models_extension import UserProfile
            
            # 确保用户有 Profile
            profile, profile_created = UserProfile.objects.get_or_create(user=user)
            
            if profile_created:
                logger.info(f"为用户 {user.username} 创建了 UserProfile")
            
            # 根据提供商设置订阅类型
            if provider == 'feishu':
                # 飞书用户自动设置为企业用户
                profile.subscription_type = UserProfile.SubscriptionType.ENTERPRISE
                profile.save()
                
                # 应用 enterprise_user 配额模板
                UserService.apply_quota_template(user.id, 'enterprise_user')
                logger.info(f"飞书用户 {user.username} 自动设置为企业用户")
            else:
                # 其他OAuth用户默认为免费用户
                if profile_created:
                    profile.subscription_type = UserProfile.SubscriptionType.FREE
                    profile.save()
                    logger.info(f"OAuth用户 {user.username} ({provider}) 设置为免费用户")
                
        except Exception as e:
            logger.error(f"为用户 {user.username} 处理 UserProfile 失败: {e}")
        
        return user, account, True
    
    @staticmethod
    @transaction.atomic
    def create_email_user(email, password, name=None):
        """
        邮箱注册
        
        Args:
            email: 邮箱地址
            password: 密码
            name: 用户名（可选）
        
        Returns:
            (user, account): 用户对象、账号对象
        """
        
        # 检查邮箱是否已存在
        if User.objects.filter(email=email).exists():
            raise ValueError('该邮箱已被注册')
        
        # 创建用户
        username = name or email.split('@')[0]
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        
        # 创建邮箱账号
        account = UserAccount.objects.create(
            user=user,
            type=UserAccount.AccountType.EMAIL,
            provider=UserAccount.Provider.EMAIL,
            provider_account_id=email,
            is_primary=True,
            is_verified=False,  # 需要邮箱验证
        )
        
        # 为邮箱用户创建 UserProfile
        try:
            from .models_extension import UserProfile
            profile = UserProfile.objects.create(
                user=user,
                subscription_type=UserProfile.SubscriptionType.FREE
            )
            logger.info(f"为邮箱用户 {user.username} 创建 UserProfile（免费用户）")
        except Exception as e:
            logger.error(f"为邮箱用户 {user.username} 创建 UserProfile 失败: {e}")
        
        # 发送验证邮件
        MultiAuthService.send_verification_email(user, email)
        
        return user, account
    
    @staticmethod
    def send_verification_email(user, email):
        """发送邮箱验证"""
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=24)
        
        EmailVerification.objects.create(
            user=user,
            email=email,
            token=token,
            expires_at=expires_at,
        )
        
        # TODO: 实际发送邮件
        # send_email(email, 'verify_email', {'token': token})
        
        return token
    
    @staticmethod
    def verify_email(token):
        """验证邮箱"""
        verification = EmailVerification.objects.filter(
            token=token,
            is_used=False
        ).first()
        
        if not verification:
            raise ValueError('无效的验证链接')
        
        if verification.is_expired():
            raise ValueError('验证链接已过期')
        
        # 标记为已使用
        verification.is_used = True
        verification.save()
        
        # 更新账号状态
        account = UserAccount.objects.filter(
            user=verification.user,
            provider=UserAccount.Provider.EMAIL,
            provider_account_id=verification.email
        ).first()
        
        if account:
            account.is_verified = True
            account.save()
        
        return verification.user
    
    @staticmethod
    def link_account(user, provider, provider_account_id, profile_data, tokens):
        """
        为已存在用户绑定新的登录方式
        
        Args:
            user: 用户对象
            provider: 提供商
            provider_account_id: 提供商账号ID
            profile_data: 用户信息
            tokens: OAuth令牌
        
        Returns:
            account: 新创建的账号对象
        """
        
        # 检查是否已绑定
        if user.has_provider(provider):
            raise ValueError(f'已绑定{provider}账号')
        
        # 检查提供商账号是否已被其他用户使用
        existing = UserAccount.objects.filter(
            provider=provider,
            provider_account_id=provider_account_id
        ).first()
        
        if existing:
            raise ValueError('该账号已被其他用户绑定')
        
        # 创建新账号关联
        account = UserAccount.objects.create(
            user=user,
            type=UserAccount.AccountType.OAUTH,
            provider=provider,
            provider_account_id=provider_account_id,
            access_token=tokens.get('access_token'),
            refresh_token=tokens.get('refresh_token'),
            expires_at=tokens.get('expires_at'),
            is_verified=True,
            provider_profile=profile_data,
        )
        
        return account
    
    @staticmethod
    def unlink_account(user, provider):
        """
        解绑登录方式
        
        Args:
            user: 用户对象
            provider: 提供商
        """
        
        # 检查是否为唯一登录方式
        if user.accounts.count() <= 1:
            raise ValueError('不能解绑唯一的登录方式')
        
        account = user.get_account_by_provider(provider)
        if not account:
            raise ValueError(f'未绑定{provider}账号')
        
        # 如果是主账号，需要指定新的主账号
        if account.is_primary:
            other_account = user.accounts.exclude(id=account.id).first()
            other_account.is_primary = True
            other_account.save()
        
        account.delete()
        return True
    
    @staticmethod
    def set_primary_account(user, provider):
        """设置主账号"""
        account = user.get_account_by_provider(provider)
        if not account:
            raise ValueError(f'未绑定{provider}账号')
        
        # 设为主账号（save方法会自动处理其他账号）
        account.is_primary = True
        account.save()
        
        return account


class FeishuAuthService:
    """飞书认证服务（示例）"""
    
    @staticmethod
    def handle_callback(code, state):
        """处理飞书回调"""
        
        # 1. 验证 state
        oauth_state = OAuthState.objects.filter(
            state=state,
            provider='feishu'
        ).first()
        
        if not oauth_state or oauth_state.is_expired():
            raise ValueError('无效或过期的认证状态')
        
        # 2. 获取令牌
        tokens = FeishuAuthService.exchange_code_for_tokens(code)
        
        # 3. 获取用户信息
        user_info = FeishuAuthService.get_user_info(tokens['access_token'])
        
        # 4. 创建或登录用户
        user, account, created = MultiAuthService.create_or_login_oauth_user(
            provider=UserAccount.Provider.FEISHU,
            provider_account_id=user_info['open_id'],
            profile_data={
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'avatar_url': user_info.get('avatar_url'),
                'nickname': user_info.get('name'),
                'open_id': user_info['open_id'],
                'union_id': user_info.get('union_id'),
                'mobile': user_info.get('mobile'),
                'department_ids': user_info.get('department_ids'),
            },
            tokens={
                'access_token': tokens['access_token'],
                'refresh_token': tokens['refresh_token'],
                'expires_at': timezone.now() + timedelta(seconds=tokens['expires_in']),
                'scope': tokens.get('scope'),
            }
        )
        
        # 5. 清理 state
        oauth_state.delete()
        
        return user, account, created
    
    @staticmethod
    def exchange_code_for_tokens(code):
        """用授权码换取令牌"""
        # TODO: 实际调用飞书API
        return {
            'access_token': 'mock_access_token',
            'refresh_token': 'mock_refresh_token',
            'expires_in': 7200,
            'scope': 'user:read',
        }
    
    @staticmethod
    def get_user_info(access_token):
        """获取用户信息"""
        # TODO: 实际调用飞书API
        return {
            'open_id': 'mock_open_id',
            'union_id': 'mock_union_id',
            'name': '测试用户',
            'email': 'test@example.com',
            'avatar_url': 'https://example.com/avatar.jpg',
            'mobile': '13800138000',
            'department_ids': ['dept_1', 'dept_2'],
        }


class GoogleAuthService:
    """Google认证服务"""
    
    @staticmethod
    def exchange_code_for_tokens(code, redirect_uri):
        """
        用授权码换取访问令牌
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
        
        Returns:
            包含access_token的字典
        """
        import requests
        import os
        
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'code': code,
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Google token exchange failed: {response.text}")
            return None
    
    @staticmethod
    def get_user_info(access_token):
        """
        获取Google用户信息
        
        Args:
            access_token: 访问令牌
        
        Returns:
            用户信息字典
        """
        import requests
        
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(user_info_url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get Google user info: {response.text}")
            return None
    
    @staticmethod
    def handle_callback(code, redirect_uri):
        """
        处理Google OAuth回调
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
        
        Returns:
            (user, account, created) 元组
        """
        # 1. 换取访问令牌
        tokens = GoogleAuthService.exchange_code_for_tokens(code, redirect_uri)
        if not tokens:
            raise Exception("Failed to exchange code for tokens")
        
        # 2. 获取用户信息
        user_info = GoogleAuthService.get_user_info(tokens['access_token'])
        if not user_info:
            raise Exception("Failed to get user info")
        
        # 3. 创建或登录用户
        user, account, created = MultiAuthService.create_or_login_oauth_user(
            provider='google',
            provider_account_id=user_info['id'],
            profile_data={
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'avatar_url': user_info.get('picture'),
                'verified_email': user_info.get('verified_email', False)
            },
            tokens={
                'access_token': tokens['access_token'],
                'refresh_token': tokens.get('refresh_token'),
                'expires_in': tokens.get('expires_in')
            }
        )
        
        return user, account, created


# 使用示例
if __name__ == '__main__':
    # 1. OAuth登录（飞书）
    user, account, created = FeishuAuthService.handle_callback('auth_code', 'state_token')
    
    # 2. 邮箱注册
    user, account = MultiAuthService.create_email_user('user@example.com', 'password123')
    
    # 3. 为已存在用户绑定Google账号
    MultiAuthService.link_account(
        user=user,
        provider='google',
        provider_account_id='google_sub_id',
        profile_data={'email': 'user@gmail.com'},
        tokens={'access_token': 'google_token'}
    )
    
    # 4. 解绑账号
    MultiAuthService.unlink_account(user, 'google')
    
    # 5. 设置主账号
    MultiAuthService.set_primary_account(user, 'feishu')