"""
邮箱认证服务
"""

import os
import random
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone
from authentication.models import UserAccount
from .utils.state_utils import StateManager
from .utils.user_utils import UserProfileManager
from .utils.token_utils import TokenManager

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailAuthService:
    """邮箱认证服务"""
    
    @staticmethod
    def send_verification_code(email, password):
        """
        发送邮箱验证码
        
        Args:
            email: 邮箱地址
            password: 密码（用于注册）
            
        Returns:
            dict: 包含状态和消息的字典
        """
        # 验证邮箱格式
        try:
            validate_email(email)
        except ValidationError:
            return {
                'success': False,
                'error': '邮箱格式不正确'
            }
        
        # 生成验证码
        code = EmailAuthService._generate_verification_code()
        
        # 缓存验证信息
        StateManager.cache_verification_data(
            email=email,
            code=code,
            password=password,
            expire_minutes=settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
        )
        
        # 发送邮件
        try:
            from_email = settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
            
            send_mail(
                subject=f'{settings.SITE_NAME or "X平台"} - 邮箱验证码',
                message=EmailAuthService._format_verification_email(code),
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            
            logger.info(f"发送验证码到邮箱 {email}")
            
            return {
                'success': True,
                'message': f'验证码已发送到 {email}'
            }
            
        except Exception as e:
            logger.error(f"发送验证码邮件失败: {e}")
            return {
                'success': False,
                'error': '发送验证码失败，请稍后重试'
            }
    
    @staticmethod
    def verify_code_and_create_user(email, code):
        """
        验证邮箱验证码并创建用户
        
        Args:
            email: 邮箱地址
            code: 验证码
            
        Returns:
            dict: 包含用户信息或错误的字典
        """
        # 获取验证数据
        verification_data = StateManager.get_verification_data(email)
        
        if not verification_data:
            return {
                'success': False,
                'error': '验证码已过期，请重新获取'
            }
        
        # 检查尝试次数
        if verification_data['attempts'] >= 5:
            StateManager.clear_verification_data(email)
            return {
                'success': False,
                'error': '验证码错误次数过多，请重新获取'
            }
        
        # 验证码匹配
        if code != verification_data['code']:
            verification_data['attempts'] += 1
            StateManager.update_verification_attempts(
                email, 
                verification_data,
                settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
            )
            return {
                'success': False,
                'error': f'验证码错误，还有{5 - verification_data["attempts"]}次机会'
            }
        
        # 验证成功，创建用户
        try:
            user = EmailAuthService._create_email_user(email, verification_data['password'])
            
            # 创建邮箱账号记录
            account = UserProfileManager.create_user_account(
                user=user,
                provider=UserAccount.Provider.EMAIL,
                provider_account_id=email,
                account_type=UserAccount.AccountType.EMAIL,
                is_verified=True,
                last_used_at=timezone.now()
            )
            
            # 创建UserProfile
            UserProfileManager.ensure_user_profile(user)
            
            # 清除缓存
            StateManager.clear_verification_data(email)
            
            # 生成JWT令牌
            tokens = TokenManager.generate_jwt_tokens(user)
            
            return {
                'success': True,
                'user': user,
                'tokens': tokens,
                'is_new_user': True
            }
            
        except Exception as e:
            logger.error(f"创建邮箱用户失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': '创建账号失败，请稍后重试'
            }
    
    @staticmethod
    def login_or_register(email, password):
        """
        邮箱登录或注册
        
        Args:
            email: 邮箱地址
            password: 密码
            
        Returns:
            dict: 操作结果
        """
        # 查找用户
        user = User.objects.filter(email=email).first()
        
        if user:
            # 用户存在，验证密码
            if user.check_password(password):
                # 更新或创建邮箱账号记录
                email_account, created = UserAccount.objects.get_or_create(
                    user=user,
                    provider=UserAccount.Provider.EMAIL,
                    defaults={
                        'type': UserAccount.AccountType.EMAIL,
                        'provider_account_id': email,
                        'is_verified': True
                    }
                )
                
                # 更新最后使用时间
                email_account.last_used_at = timezone.now()
                email_account.save()
                
                # 生成JWT令牌
                tokens = TokenManager.generate_jwt_tokens(user)
                
                return {
                    'success': True,
                    'user': user,
                    'tokens': tokens,
                    'is_new_user': False
                }
            else:
                return {
                    'success': False,
                    'error': '密码错误'
                }
        else:
            # 新用户，发送验证码
            result = EmailAuthService.send_verification_code(email, password)
            if result['success']:
                return {
                    'success': True,
                    'require_verification': True,
                    'email': email,
                    'message': result['message']
                }
            else:
                return result
    
    @staticmethod
    def resend_verification_code(email):
        """
        重新发送验证码
        
        Args:
            email: 邮箱地址
            
        Returns:
            dict: 操作结果
        """
        # 检查是否存在待验证信息
        verification_data = StateManager.get_verification_data(email)
        
        if not verification_data:
            return {
                'success': False,
                'error': '请先进行登录操作'
            }
        
        # 生成新验证码
        code = EmailAuthService._generate_verification_code()
        
        # 更新缓存
        verification_data['code'] = code
        verification_data['attempts'] = 0
        StateManager.update_verification_attempts(
            email,
            verification_data,
            settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES
        )
        
        # 发送邮件
        try:
            from_email = settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL
            
            send_mail(
                subject=f'{settings.SITE_NAME or "X平台"} - 新的验证码',
                message=EmailAuthService._format_resend_email(code),
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            
            logger.info(f"重新发送验证码到邮箱 {email}")
            
            return {
                'success': True,
                'message': f'新验证码已发送到 {email}'
            }
            
        except Exception as e:
            logger.error(f"重发验证码邮件失败: {e}")
            return {
                'success': False,
                'error': '发送验证码失败，请稍后重试'
            }
    
    @staticmethod
    def _generate_verification_code():
        """生成6位验证码"""
        return ''.join([str(random.randint(0, 9)) for _ in range(settings.EMAIL_VERIFICATION_CODE_LENGTH)])
    
    @staticmethod
    def _create_email_user(email, password):
        """
        创建邮箱用户
        
        Args:
            email: 邮箱地址
            password: 密码
            
        Returns:
            User: 创建的用户对象
        """
        username_base = email.split('@')[0]
        username = UserProfileManager.generate_unique_username(username_base)
        
        # 创建用户
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # 设置用户状态
        user.status = UserProfileManager.determine_user_status('email')
        user.is_active = True  # Django的is_active字段保持True
        user.save()
        
        status_text = "激活" if user.status == User.Status.ACTIVE else "未激活"
        logger.info(f"邮箱注册用户 {user.email} 创建成功，状态设为{status_text}({user.status})")
        
        return user
    
    @staticmethod
    def _format_verification_email(code):
        """格式化验证邮件内容"""
        return f'''您好！
        
您正在注册{settings.SITE_NAME or "X平台"}账号。

您的验证码是：{code}

验证码有效期为{settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES}分钟，请尽快完成验证。

如果这不是您的操作，请忽略此邮件。

祝好！
{settings.SITE_NAME or "X平台"}团队'''
    
    @staticmethod
    def _format_resend_email(code):
        """格式化重发验证邮件内容"""
        return f'''您好！

您的新验证码是：{code}

验证码有效期为{settings.EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES}分钟，请尽快完成验证。

如果这不是您的操作，请忽略此邮件。

祝好！
{settings.SITE_NAME or "X平台"}团队'''