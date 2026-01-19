"""
认证中间件 - 确保登录用户有UserProfile
"""

import logging
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from .models_extension import UserProfile
from .models import UserAccount
from .user_service import UserService

logger = logging.getLogger(__name__)
User = get_user_model()


class EnsureUserProfileMiddleware(MiddlewareMixin):
    """
    确保每个已认证用户都有UserProfile的中间件
    """
    
    def process_request(self, request):
        """
        在每个请求处理前检查用户是否有UserProfile
        """
        # 只处理已认证的用户
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                # 检查用户是否有profile
                if not hasattr(request.user, 'profile'):
                    # 判断用户类型
                    subscription_type = UserProfile.SubscriptionType.FREE
                    
                    # 检查是否为飞书用户
                    if UserAccount.objects.filter(user=request.user, provider='feishu').exists():
                        subscription_type = UserProfile.SubscriptionType.ENTERPRISE
                    
                    # 创建UserProfile
                    profile = UserProfile.objects.create(
                        user=request.user,
                        subscription_type=subscription_type
                    )
                    
                    logger.info(f"中间件为用户 {request.user.username} 创建了UserProfile (订阅类型: {subscription_type})")
                    
                    # 如果是飞书用户，应用enterprise_user配额模板
                    if subscription_type == UserProfile.SubscriptionType.ENTERPRISE:
                        try:
                            UserService.apply_quota_template(request.user.id, 'enterprise_user')
                            logger.info(f"为飞书用户 {request.user.username} 应用了企业用户配额模板")
                        except Exception as e:
                            logger.error(f"为用户 {request.user.username} 应用配额模板失败: {e}")
                            
            except Exception as e:
                # 记录错误但不阻断请求
                logger.error(f"检查/创建用户 {request.user.username} 的UserProfile时出错: {e}", exc_info=True)
        
        return None  # 继续处理请求