"""
frago Cloud Market URL 路由配置

路由结构:
- /auth/device/code - 获取设备认证码
- /auth/device/token - 轮询获取 Token
- /auth/device/authorize - 用户授权设备码
- /auth/me - 获取当前用户信息
- /auth/refresh - 刷新 Token
- /recipes/ - Recipe 列表和发布
- /recipes/<id>/ - Recipe 详情
- /recipes/<id>/download - 下载 Recipe
- /recipes/<id>/rate - 评分 Recipe
- /sync/sessions/ - 同步会话列表和上传
- /sync/sessions/<id>/ - 下载/删除同步会话
"""

from django.urls import path

from .views import (
    DeviceCodeView,
    DeviceTokenView,
    DeviceAuthorizeView,
    UserInfoView,
    TokenRefreshView,
    RecipeListView,
    RecipeDetailView,
    RecipeDownloadView,
    RecipePublishView,  # Phase 5 (US3)
    RecipeRateView,  # Phase 6 (US4)
    # Claude Code 镜像视图（US6）
    ClaudeCodeVersionListView,
    ClaudeCodeLatestView,
    ClaudeCodeDownloadView,
)

app_name = 'market'

urlpatterns = [
    # 设备认证端点 - Phase 3 (US1)
    path('auth/device/code', DeviceCodeView.as_view(), name='device-code'),
    path('auth/device/token', DeviceTokenView.as_view(), name='device-token'),
    path('auth/device/authorize', DeviceAuthorizeView.as_view(), name='device-authorize'),
    path('auth/me', UserInfoView.as_view(), name='user-info'),
    path('auth/refresh', TokenRefreshView.as_view(), name='token-refresh'),

    # Recipe 市场端点 - Phase 4 (US2) + Phase 5 (US3)
    path('recipes/', RecipeListView.as_view(), name='recipe-list'),
    path('recipes/publish', RecipePublishView.as_view(), name='recipe-publish'),  # Phase 5 (US3)
    path('recipes/<int:pk>/', RecipeDetailView.as_view(), name='recipe-detail'),
    path('recipes/<int:pk>/download', RecipeDownloadView.as_view(), name='recipe-download'),
    path('recipes/<int:pk>/rate', RecipeRateView.as_view(), name='recipe-rate'),  # Phase 6 (US4)

    # 会话同步端点 - Phase 7 (US5) 实现
    # path('sync/sessions/', SessionListView.as_view(), name='session-list'),
    # path('sync/sessions/<uuid:pk>/', SessionDetailView.as_view(), name='session-detail'),

    # Claude Code 镜像端点 - Phase 9 (US6)
    path('claude-code/versions', ClaudeCodeVersionListView.as_view(), name='claude-code-versions'),
    path('claude-code/latest', ClaudeCodeLatestView.as_view(), name='claude-code-latest'),
    path('claude-code/download/<str:platform_arch>', ClaudeCodeDownloadView.as_view(), name='claude-code-download'),
]
