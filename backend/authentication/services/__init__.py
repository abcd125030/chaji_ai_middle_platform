"""
认证服务模块

提供统一的认证服务接口
"""

from .oauth_service import OAuthService, GoogleAuthService, FeishuAuthService
from .email_service import EmailAuthService
from .user_management_service import UserManagementService
from .multi_auth_service import MultiAuthService

__all__ = [
    'OAuthService',
    'GoogleAuthService',
    'FeishuAuthService',
    'EmailAuthService', 
    'UserManagementService',
    'MultiAuthService'
]