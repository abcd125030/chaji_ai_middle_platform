"""
AI处理器模块
"""
from .base_processor import BaseAIProcessor
from .qwen_processor import QwenProcessor

__all__ = [
    'BaseAIProcessor',
    'QwenProcessor'
]