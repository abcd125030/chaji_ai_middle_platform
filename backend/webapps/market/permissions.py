"""
frago Cloud Market 权限类

提供 Premium 用户检查等权限控制
"""

from rest_framework.permissions import BasePermission
from authentication.models_extension import UserProfile


class IsPremiumUser(BasePermission):
    """
    检查用户是否为 Premium 用户（VIP、Enterprise 或 Max）

    用于限制 Premium Recipe 的下载权限
    """
    message = '此 Recipe 需要订阅才能下载'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            profile = request.user.profile
            return profile.subscription_type in [
                UserProfile.SubscriptionType.VIP,
                UserProfile.SubscriptionType.ENTERPRISE,
                UserProfile.SubscriptionType.MAX,
            ]
        except UserProfile.DoesNotExist:
            return False


class IsRecipeAuthor(BasePermission):
    """
    检查用户是否为 Recipe 作者

    用于限制 Recipe 编辑和删除权限
    """
    message = '只有作者才能修改此 Recipe'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.author == request.user


class IsSessionOwner(BasePermission):
    """
    检查用户是否为会话所有者

    用于限制会话的访问和删除权限
    """
    message = '只有会话所有者才能访问此会话'

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        return obj.user == request.user


class CanSyncSession(BasePermission):
    """
    检查用户是否有会话同步配额

    FREE 用户每月 5 个会话
    VIP/Enterprise/Max 用户无限制
    """
    message = '会话同步配额已用完'

    # 免费用户每月同步配额
    FREE_MONTHLY_QUOTA = 5

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            profile = request.user.profile
            # Premium 用户无限制
            if profile.subscription_type in [
                UserProfile.SubscriptionType.VIP,
                UserProfile.SubscriptionType.ENTERPRISE,
                UserProfile.SubscriptionType.MAX,
            ]:
                return True

            # 免费用户检查月度配额
            from django.utils import timezone
            from .models import SyncedSession

            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            monthly_count = SyncedSession.objects.filter(
                user=request.user,
                created_at__gte=month_start
            ).count()

            return monthly_count < self.FREE_MONTHLY_QUOTA

        except UserProfile.DoesNotExist:
            return False
