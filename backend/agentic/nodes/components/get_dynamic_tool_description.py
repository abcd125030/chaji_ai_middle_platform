# -*- coding: utf-8 -*-
"""
get_dynamic_tool_description.py

动态生成可用工具的描述字符串。
"""


def get_dynamic_tool_description() -> str:
    """
    动态生成可用工具的描述字符串。
    调用 planner.py 的实现。
    """
    from ..planner import get_tool_descriptions_for_prompt
    return get_tool_descriptions_for_prompt()