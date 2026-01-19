# -*- coding: utf-8 -*-
"""
get_dynamic_capability_map.py

基于当前状态动态生成能力映射描述。
"""

from typing import TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import RuntimeState


def get_dynamic_capability_map(state: 'RuntimeState') -> str:
    """
    基于当前状态动态生成能力映射描述。
    
    注意：能力映射功能已被移除，因为它增加了不必要的抽象层。
    现在直接使用工具描述即可。
    """
    # 能力映射功能已废弃，返回空字符串
    return ""