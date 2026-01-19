# -*- coding: utf-8 -*-
"""
safe_json_dumps.py

安全的JSON序列化工具函数。
"""

import json
from typing import Any, Optional


def safe_json_dumps(data: Any, indent: Optional[int] = 2) -> str:
    """
    安全地将数据转换为JSON格式的字符串。
    如果数据不可JSON序列化，则回退到其字符串表示。
    正确处理非ASCII字符。

    参数:
    data (Any): 任何类型的数据，尝试进行JSON序列化。
    indent (Optional[int]): JSON输出的缩进级别，默认为2。如果为None，则不缩进。

    返回:
    str: JSON格式的字符串或数据的字符串表示。
    """
    try:
        # 尝试使用 ensure_ascii=False 进行JSON序列化，以提高可读性（支持中文等非ASCII字符）
        return json.dumps(data, indent=indent, ensure_ascii=False)
    except TypeError:
        # 如果发生TypeError，可能是因为数据中包含不可序列化的对象。
        # 回退到数据的字符串表示。
        return str(data)
    except Exception:
        # 捕获其他可能的JSON序列化错误，确保总是返回一个字符串
        return str(data)
