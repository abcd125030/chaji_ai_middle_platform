# -*- coding: utf-8 -*-
# backend/agentic/utils/commons/user_context.py

"""
用户上下文获取模块。

提供统一的用户上下文信息获取功能。
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("django")


def user_context(user_id: Optional[int]) -> Dict[str, Any]:
    """
    获取用户上下文信息。
    
    参数:
    user_id: 用户ID
    
    返回:
    Dict[str, Any]: 用户上下文信息字典，至少包含user_id
    """
    user_context_data = {}
    
    if user_id:
        try:
            from authentication.user_service import UserService
            user_context_data = UserService.get_user_context(user_id)
        except Exception as e:
            logger.error(f"获取用户上下文失败: {e}")
            # 至少设置基本的用户ID
            user_context_data = {'user_id': user_id}
    
    return user_context_data