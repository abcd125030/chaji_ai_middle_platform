"""
状态管理工具函数
"""

import json
import logging
from django.core.cache import cache
from authentication.models import OAuthState

logger = logging.getLogger(__name__)


class StateManager:
    """OAuth状态管理器"""
    
    @staticmethod
    def create_oauth_state(provider, state, redirect_url, code_verifier=None, extra_data=None):
        """
        创建OAuth状态记录
        
        Args:
            provider: 提供商名称
            state: 状态令牌
            redirect_url: 重定向URL
            code_verifier: PKCE验证码
            extra_data: 额外数据
            
        Returns:
            OAuthState: 创建的状态对象
        """
        oauth_state = OAuthState.objects.create(
            provider=provider,
            state=state,
            redirect_url=redirect_url,
            code_verifier=code_verifier,
            extra_data=json.dumps(extra_data) if extra_data else None
        )
        logger.info(f"创建OAuth状态: provider={provider}, state={state}")
        return oauth_state
    
    @staticmethod
    def verify_and_get_state(state, provider=None):
        """
        验证并获取OAuth状态
        
        Args:
            state: 状态令牌
            provider: 提供商名称（可选）
            
        Returns:
            OAuthState: 状态对象，如果无效则返回None
        """
        try:
            query = {'state': state}
            if provider:
                query['provider'] = provider
            
            oauth_state = OAuthState.objects.get(**query)
            return oauth_state
        except OAuthState.DoesNotExist:
            logger.warning(f"无效的OAuth状态: state={state}, provider={provider}")
            return None
    
    @staticmethod
    def parse_extra_data(oauth_state):
        """
        解析OAuth状态的额外数据
        
        Args:
            oauth_state: OAuth状态对象
            
        Returns:
            dict: 解析后的额外数据
        """
        if oauth_state and oauth_state.extra_data:
            try:
                return json.loads(oauth_state.extra_data)
            except (json.JSONDecodeError, TypeError):
                logger.error(f"解析OAuth额外数据失败: {oauth_state.extra_data}")
        return {}
    
    @staticmethod
    def cleanup_state(oauth_state):
        """
        清理OAuth状态
        
        Args:
            oauth_state: OAuth状态对象
        """
        if oauth_state:
            oauth_state.delete()
            logger.info(f"清理OAuth状态: state={oauth_state.state}")
    
    @staticmethod
    def cache_verification_data(email, code, password, expire_minutes=10):
        """
        缓存邮箱验证数据
        
        Args:
            email: 邮箱地址
            code: 验证码
            password: 密码
            expire_minutes: 过期时间（分钟）
        """
        cache_key = f'email_verification:{email}'
        cache_data = {
            'code': code,
            'password': password,
            'attempts': 0
        }
        cache.set(cache_key, cache_data, expire_minutes * 60)
        logger.info(f"缓存验证数据: email={email}, expire={expire_minutes}分钟")
    
    @staticmethod
    def get_verification_data(email):
        """
        获取邮箱验证数据
        
        Args:
            email: 邮箱地址
            
        Returns:
            dict: 验证数据，如果不存在则返回None
        """
        cache_key = f'email_verification:{email}'
        return cache.get(cache_key)
    
    @staticmethod
    def update_verification_attempts(email, verification_data, expire_minutes=10):
        """
        更新验证尝试次数
        
        Args:
            email: 邮箱地址
            verification_data: 验证数据
            expire_minutes: 过期时间（分钟）
        """
        cache_key = f'email_verification:{email}'
        cache.set(cache_key, verification_data, expire_minutes * 60)
    
    @staticmethod
    def clear_verification_data(email):
        """
        清除验证数据
        
        Args:
            email: 邮箱地址
        """
        cache_key = f'email_verification:{email}'
        cache.delete(cache_key)
        logger.info(f"清除验证数据: email={email}")