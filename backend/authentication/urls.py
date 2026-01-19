from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import AllowAny
from .views import (
    CustomTokenVerifyView, 
    FeishuLoginView, 
    GoogleLoginView,
    EmailLoginView,
    EmailVerifyView,
    EmailResendCodeView,
    UserActivationView,
    UserListView
)
from .views_join_wish import (
    JoinWishSubmitView,
    JoinWishListView,
    JoinWishApproveView,
    JoinWishBatchApproveView
)
from .api import UserSyncAPI, WebUserSyncAPI, WebUserProfileAPI

# 创建一个允许匿名访问的 TokenRefreshView
class AnonymousTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

app_name = 'authentication'

urlpatterns = [
    # 飞书OAuth相关
    path('feishu/login/', FeishuLoginView.as_view(), name='feishu-login'),
    path('feishu/callback/', FeishuLoginView.as_view(), name='feishu-callback'),
    
    # Google OAuth相关
    path('google/login/', GoogleLoginView.as_view(), name='google-login'),
    path('google/callback/', GoogleLoginView.as_view(), name='google-callback'),
    
    # 邮箱登录相关
    path('email/login/', EmailLoginView.as_view(), name='email-login'),
    path('email/verify/', EmailVerifyView.as_view(), name='email-verify'),
    path('email/resend/', EmailResendCodeView.as_view(), name='email-resend'),
    
    # JWT令牌相关
    path('token/refresh/', AnonymousTokenRefreshView.as_view(), name='token-refresh'),
    path('token/verify/', CustomTokenVerifyView.as_view(), name='token-verify'),

    # 用户同步API
    path('sync/user/', UserSyncAPI.as_view(), name='user-sync'),
    path('sync/web-user/', WebUserSyncAPI.as_view(), name='web-user-sync'),
    
    # 用户信息API
    path('profile/', WebUserProfileAPI.as_view(), name='web-user-profile'),
    
    # 管理员用户管理API
    path('admin/users/', UserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:user_id>/activation/', UserActivationView.as_view(), name='admin-user-activation'),
    
    # Join Wish 申请相关API
    path('join-wish/submit/', JoinWishSubmitView.as_view(), name='join-wish-submit'),
    path('join-wish/list/', JoinWishListView.as_view(), name='join-wish-list'),
    path('join-wish/approve/<int:user_id>/', JoinWishApproveView.as_view(), name='join-wish-approve'),
    path('join-wish/batch-approve/', JoinWishBatchApproveView.as_view(), name='join-wish-batch-approve'),
]
