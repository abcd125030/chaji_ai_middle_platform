"""
Agentic utilities package
"""

from .user_context import build_user_context, update_runtime_state_with_user_context, build_user_prompt

__all__ = [
    'build_user_context',
    'update_runtime_state_with_user_context',
    'build_user_prompt',
]