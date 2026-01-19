# -*- coding: utf-8 -*-
"""
build_planner_prompt.py

构建简化版的 planner prompt。
"""

from typing import Dict, Any, Optional, Tuple, TYPE_CHECKING

# 使用 TYPE_CHECKING 来避免循环导入
if TYPE_CHECKING:
    from ...core.schemas import RuntimeState


def build_planner_prompt(state: 'RuntimeState', nodes_map: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """
    构建简化版的 planner prompt，分为系统提示词和用户提示词。
    直接调用 planner.py 中的实现。
    
    参数:
    state (RuntimeState): 当前运行时状态
    nodes_map (Optional[Dict[str, Any]]): 节点配置映射
    
    返回:
    tuple[str, str]: (系统提示词, 用户提示词)
    """
    # 直接调用 planner.py 的内部函数
    from ..planner import _build_prompt_internal
    return _build_prompt_internal(state, nodes_map)