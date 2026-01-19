# -*- coding: utf-8 -*-
# backend/agentic/utils/processor_serializer.py

"""
处理器序列化工具模块。

该模块提供了数据序列化相关的工具函数，用于处理 Pydantic 模型、
pandas 数据框架和其他需要序列化的对象。
"""

import sys
from typing import Any
from pydantic import BaseModel


def serialize_output(data: Any) -> Any:
    """
    递归地序列化 Pydantic 模型和具有 `to_dict` 方法的对象。
    此方法确保节点输出可以被正确地存储或传输，特别是当输出包含复杂对象时。

    参数:
    data (Any): 需要序列化的数据。

    返回:
    Any: 序列化后的数据，通常是 Python 基本类型（字典、列表、字符串、数字等）。
    """
    if isinstance(data, BaseModel):
        # 如果是 Pydantic 模型，使用 model_dump() 方法将其转换为字典
        # model_dump() 预期返回一个 JSON 可序列化的字典
        return data.model_dump()

    # 动态处理 pandas 对象，如果 pandas 模块已加载
    if 'pandas' in sys.modules:
        import pandas as pd
        if isinstance(data, pd.DataFrame):
            # 对于 DataFrame，使用 'records' 方向转换为字典列表
            return serialize_output(data.to_dict(orient='records'))
        if isinstance(data, pd.Series):
            # 对于 Series，转换为字典
            return serialize_output(data.to_dict())

    if hasattr(data, 'to_dict') and callable(getattr(data, 'to_dict')):
        # 对于其他具有 to_dict 方法的对象，递归序列化其 to_dict() 的结果
        return serialize_output(data.to_dict())
    if isinstance(data, list):
        # 如果是列表，递归序列化列表中的每个元素
        return [serialize_output(item) for item in data]
    if isinstance(data, dict):
        # 如果是字典，递归序列化字典中的每个值
        return {k: serialize_output(v) for k, v in data.items()}
    # 对于基本类型（如字符串、数字、布尔值、None），直接返回
    return data