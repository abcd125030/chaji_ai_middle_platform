"""
Token相关工具函数
"""

import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken
import logging

logger = logging.getLogger(__name__)


class TokenManager:
    """Token管理器"""
    
    @staticmethod
    def generate_state_token(length=16):
        """生成状态令牌"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_code_verifier():
        """生成PKCE验证码"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_code_challenge(code_verifier):
        """生成PKCE挑战码"""
        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
        code_challenge = code_challenge.replace('=', '')  # 移除填充
        return code_challenge
    
    @staticmethod
    def generate_jwt_tokens(user):
        """
        为用户生成JWT令牌
        
        Args:
            user: 用户对象
            
        Returns:
            dict: 包含access和refresh令牌的字典
        """
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        return {
            'access': str(access_token),
            'refresh': str(refresh),
            'token_type': 'Bearer'
        }
    
    @staticmethod
    def calculate_token_expiry(expires_in):
        """
        计算令牌过期时间
        
        Args:
            expires_in: 过期秒数
            
        Returns:
            datetime: 过期时间
        """
        if expires_in:
            return timezone.now() + timedelta(seconds=expires_in)
        return None