"""
共享工具函数模块

提供跨工具共享的通用功能，包括：
- user_profile: 用户画像提取
- runtime_context: 运行时上下文提取
"""

from .user_profile import get_user_profile
from .runtime_context import extract_runtime_contexts

__all__ = [
    'get_user_profile',
    'extract_runtime_contexts'
]