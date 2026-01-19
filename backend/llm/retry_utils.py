"""
LLM服务重试工具类
提供智能重试机制，处理网络错误和服务不可用等情况
"""
import time
import logging
import random
from typing import Callable, Any, Optional, Dict, List
from functools import wraps

logger = logging.getLogger(__name__)


class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class LLMRetryHandler:
    """LLM调用重试处理器"""
    
    # 可重试的异常类型和对应的友好描述
    RETRYABLE_ERRORS = {
        'ConnectionError': '网络连接异常，无法连接到AI服务',
        'ConnectionResetError': 'AI服务连接被中断',
        'Timeout': 'AI服务响应超时',
        'ReadTimeout': 'AI服务读取超时',
        'ConnectTimeout': 'AI服务连接超时',
        'SSLError': '安全连接建立失败',
        'ProxyError': '代理服务器连接异常',
        'HTTPError': 'AI服务HTTP请求失败',
    }
    
    # 不可重试的异常（需要立即失败）
    NON_RETRYABLE_ERRORS = {
        'AuthenticationError': '认证失败，请检查API密钥',
        'InvalidRequestError': '请求参数无效',
        'RateLimitError': 'API调用频率超限',
        'InsufficientQuotaError': 'API额度不足',
    }
    
    @staticmethod
    def get_error_description(error: Exception) -> tuple[str, bool]:
        """
        获取错误的友好描述和是否可重试
        返回: (错误描述, 是否可重试)
        """
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # 检查是否是可重试的错误
        for err_name, description in LLMRetryHandler.RETRYABLE_ERRORS.items():
            if err_name.lower() in error_type.lower() or err_name.lower() in error_str:
                return description, True
        
        # 检查是否是不可重试的错误
        for err_name, description in LLMRetryHandler.NON_RETRYABLE_ERRORS.items():
            if err_name.lower() in error_type.lower() or err_name.lower() in error_str:
                return description, False
        
        # 特殊处理一些常见的错误码
        if 'errno 54' in error_str or 'connection reset by peer' in error_str:
            return 'AI服务连接被远程服务器重置', True
        elif 'errno 60' in error_str or 'operation timed out' in error_str:
            return 'AI服务操作超时', True
        elif 'errno 61' in error_str or 'connection refused' in error_str:
            return 'AI服务拒绝连接', True
        elif '401' in error_str or 'unauthorized' in error_str:
            return 'API认证失败，请检查密钥配置', False
        elif '403' in error_str or 'forbidden' in error_str:
            return 'API访问被禁止，请检查权限', False
        elif '429' in error_str or 'rate limit' in error_str:
            return 'API请求频率超限，请稍后重试', True
        elif '500' in error_str or '502' in error_str or '503' in error_str:
            return 'AI服务暂时不可用', True
        
        # 默认情况
        return f'AI服务调用失败', False
    
    @staticmethod
    def calculate_delay(attempt: int, config: RetryConfig) -> float:
        """计算重试延迟时间"""
        delay = min(
            config.initial_delay * (config.exponential_base ** (attempt - 1)),
            config.max_delay
        )
        
        if config.jitter:
            # 添加随机抖动，避免同时重试
            delay = delay * (0.5 + random.random())
        
        return delay
    
    @staticmethod
    def retry_with_backoff(
        func: Callable,
        config: Optional[RetryConfig] = None,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None
    ) -> Any:
        """
        使用退避策略执行重试
        
        Args:
            func: 要执行的函数
            config: 重试配置
            on_retry: 重试时的回调函数(attempt, error, delay)
        """
        if config is None:
            config = RetryConfig()
        
        last_error = None
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                return func()
            except Exception as e:
                last_error = e
                error_desc, is_retryable = LLMRetryHandler.get_error_description(e)
                
                # 如果不可重试，立即失败
                if not is_retryable:
                    logger.info(f"LLM调用遇到不可重试的错误: {error_desc}")
                    raise
                
                # 如果是最后一次尝试，失败
                if attempt >= config.max_attempts:
                    logger.info(f"LLM调用在{attempt}次尝试后失败: {error_desc}")
                    raise
                
                # 计算延迟
                delay = LLMRetryHandler.calculate_delay(attempt, config)
                
                # 记录重试信息
                logger.info(
                    f"LLM调用第{attempt}次尝试失败: {error_desc}，"
                    f"将在{delay:.2f}秒后进行第{attempt+1}次尝试"
                )
                
                # 调用重试回调
                if on_retry:
                    on_retry(attempt, e, delay)
                
                # 等待后重试
                time.sleep(delay)
        
        # 不应该到达这里
        raise last_error


def with_retry(config: Optional[RetryConfig] = None):
    """
    装饰器：为函数添加重试功能
    
    使用示例:
        @with_retry(RetryConfig(max_attempts=3))
        def call_api():
            return requests.post(...)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return LLMRetryHandler.retry_with_backoff(
                lambda: func(*args, **kwargs),
                config
            )
        return wrapper
    return decorator