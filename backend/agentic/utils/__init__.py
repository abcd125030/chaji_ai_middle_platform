# -*- coding: utf-8 -*-
# backend/agentic/utils/__init__.py

"""
处理器工具模块。

该模块包含了处理器相关的各种工具函数和子模块。
"""

from .processor_serializer import serialize_output
# 延迟导入 processor_tool_executor 以避免循环导入
# from .processor_tool_executor import execute_tool, get_tool_config
from .processor_state import (
    load_session_states,
    create_state_with_history,
    create_initial_state
)
from .processor_graph import load_callable, find_next_node_name

# 动态导入函数以避免循环导入
def get_tool_config(*args, **kwargs):
    from .processor_tool_executor import get_tool_config as _get_tool_config
    return _get_tool_config(*args, **kwargs)

def execute_tool(*args, **kwargs):
    from .processor_tool_executor import execute_tool as _execute_tool
    return _execute_tool(*args, **kwargs)

__all__ = [
    'serialize_output',
    'execute_tool',
    'get_tool_config',
    'load_session_states',
    'create_state_with_history',
    'create_initial_state',
    'load_callable',
    'find_next_node_name'
]