"""
OAuth认证服务
"""

import os
import requests
import logging
from abc import ABC, abstractmethod
from urllib.parse import urlencode
from django.conf import settings
from .multi_auth_service import MultiAuthService
from .utils.token_utils import TokenManager
from .utils.state_utils import StateManager

logger = logging.getLogger(__name__)


class OAuthService(ABC):
    """OAuth服务基类"""
    
    @abstractmethod
    def get_authorization_url(self, state, redirect_uri, **kwargs):
        """获取授权URL"""
        pass
    
    @abstractmethod
    def exchange_code_for_tokens(self, code, redirect_uri, **kwargs):
        """用授权码换取访问令牌"""
        pass
    
    @abstractmethod
    def get_user_info(self, access_token):
        """获取用户信息"""
        pass
    
    @abstractmethod
    def handle_callback(self, code, redirect_uri, **kwargs):
        """处理OAuth回调"""
        pass


class GoogleAuthService(OAuthService):
    """Google OAuth认证服务"""
    
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def get_authorization_url(self, state, redirect_uri, **kwargs):
        """
        生成Google授权URL
        
        Args:
            state: 状态令牌
            redirect_uri: 重定向URI
            **kwargs: 其他参数
            
        Returns:
            str: 授权URL
        """
        params = {
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': kwargs.get('scope', 'openid email profile'),
            'state': state,
            'access_type': 'offline',
            'prompt': 'select_account'
        }
        
        auth_url = f"{self.AUTH_URL}?{urlencode(params)}"
        logger.info(f"生成Google授权URL: redirect_uri={redirect_uri}")
        
        return auth_url
    
    def exchange_code_for_tokens(self, code, redirect_uri, **kwargs):
        """
        用授权码换取访问令牌
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
            **kwargs: 其他参数
            
        Returns:
            dict: 包含access_token的字典，失败返回None
        """
        data = {
            'code': code,
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info("成功获取Google访问令牌")
            
            return token_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Google token exchange failed: {e}")
            logger.error(f"Response: {response.text if 'response' in locals() else 'N/A'}")
            return None
    
    def get_user_info(self, access_token):
        """
        获取Google用户信息
        
        Args:
            access_token: 访问令牌
            
        Returns:
            dict: 用户信息字典，失败返回None
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            response = requests.get(self.USER_INFO_URL, headers=headers)
            response.raise_for_status()
            
            user_info = response.json()
            logger.info(f"成功获取Google用户信息: {user_info.get('email')}")
            
            return user_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Google user info: {e}")
            return None
    
    def handle_callback(self, code, redirect_uri, **kwargs):
        """
        处理Google OAuth回调
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
            **kwargs: 其他参数
            
        Returns:
            tuple: (user, account, created) 元组
        """
        # 1. 换取访问令牌
        tokens = self.exchange_code_for_tokens(code, redirect_uri)
        if not tokens:
            raise Exception("Failed to exchange code for tokens")
        
        # 2. 获取用户信息
        user_info = self.get_user_info(tokens['access_token'])
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


class FeishuAuthService(OAuthService):
    """飞书OAuth认证服务"""
    
    def __init__(self):
        self.app_id = settings.FEISHU['APP_ID']
        self.app_secret = settings.FEISHU['APP_SECRET']
        self.auth_url = settings.FEISHU['OAUTH']['AUTHORIZATION_URL']
        self.token_url = settings.FEISHU['OAUTH']['ACCESS_TOKEN_URL']
        self.user_info_url = settings.FEISHU['OAUTH']['USER_INFO_URL']
        self.redirect_uri = settings.FEISHU['OAUTH']['REDIRECT_URI']
        self.scopes = settings.FEISHU['OAUTH']['SCOPES']
        self.pkce_enabled = settings.FEISHU['OAUTH'].get('PKCE_ENABLED', True)
    
    def get_authorization_url(self, state, redirect_uri, **kwargs):
        """
        生成飞书授权URL
        
        Args:
            state: 状态令牌
            redirect_uri: 重定向URI
            **kwargs: 可包含code_verifier用于PKCE
            
        Returns:
            str: 授权URL
        """
        params = {
            'client_id': self.app_id,
            'response_type': 'code',
            'state': state,
            'redirect_uri': redirect_uri or self.redirect_uri,
            'scope': ' '.join(self.scopes),
        }
        
        # 如果启用了PKCE
        if self.pkce_enabled and kwargs.get('code_challenge'):
            params.update({
                'code_challenge': kwargs['code_challenge'],
                'code_challenge_method': 'S256'
            })
        
        auth_url = f"{self.auth_url}?{urlencode(params)}"
        logger.info(f"生成飞书授权URL: scopes={params['scope']}")
        
        return auth_url
    
    def exchange_code_for_tokens(self, code, redirect_uri, **kwargs):
        """
        获取飞书访问令牌
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
            **kwargs: 可包含code_verifier用于PKCE
            
        Returns:
            dict: 令牌数据
        """
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'code': code,
            'redirect_uri': redirect_uri or self.redirect_uri,
            'scope': ' '.join(self.scopes),
        }
        
        # 如果启用了PKCE且存在code_verifier
        if self.pkce_enabled and kwargs.get('code_verifier'):
            data['code_verifier'] = kwargs['code_verifier']
        
        try:
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            logger.info(f"飞书token获取成功，包含refresh_token: {'refresh_token' in token_data}")
            
            return token_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取飞书token失败: {e}")
            logger.error(f"Response: {response.text if 'response' in locals() else 'N/A'}")
            return None
    
    def get_user_info(self, access_token):
        """
        获取飞书用户信息
        
        Args:
            access_token: 访问令牌
            
        Returns:
            dict: 用户信息
        """
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(self.user_info_url, headers=headers)
            response.raise_for_status()
            
            user_info = response.json()
            logger.info(f"成功获取飞书用户信息: {user_info.get('data', {}).get('name')}")
            
            return user_info
            
        except Exception as e:
            logger.error(f"获取飞书用户信息失败: {e}")
            return None
    
    def handle_callback(self, code, redirect_uri, **kwargs):
        """
        处理飞书OAuth回调
        
        Args:
            code: 授权码
            redirect_uri: 重定向URI
            **kwargs: 其他参数（如code_verifier）
            
        Returns:
            tuple: (user, account, created)
        """
        # 1. 获取访问令牌
        tokens = self.exchange_code_for_tokens(code, redirect_uri, **kwargs)
        if not tokens:
            raise Exception("Failed to get Feishu access token")
        
        # 2. 获取用户信息
        user_info_response = self.get_user_info(tokens['access_token'])
        if not user_info_response or user_info_response.get('code') != 0:
            raise Exception("Failed to get Feishu user info")
        
        user_data = user_info_response['data']
        
        # 3. 准备用户信息数据
        profile_data = {
            'email': user_data.get('email', f"{user_data['open_id']}@feishu.users"),
            'name': user_data.get('name', f"feishu_{user_data['open_id']}"),
            'avatar_url': user_data.get('avatar_url', ''),
            'nickname': user_data.get('name'),
            'open_id': user_data['open_id'],
            'union_id': user_data.get('union_id'),
            'mobile': user_data.get('mobile'),
            'department_ids': user_data.get('department_ids'),
        }
        
        # 4. 准备令牌信息
        token_info = {
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
            'expires_in': tokens.get('expires_in'),
            'token_type': tokens.get('token_type'),
            'scope': tokens.get('scope'),
        }
        
        # 5. 创建或登录用户
        user, account, created = MultiAuthService.create_or_login_oauth_user(
            provider='feishu',
            provider_account_id=user_data['open_id'],
            profile_data=profile_data,
            tokens=token_info
        )
        
        return user, account, created