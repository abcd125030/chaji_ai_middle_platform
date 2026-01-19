# -*- coding: utf-8 -*-
"""
replace_data_markers.py

处理工具输入中的数据标记替换。
支持 ${路径} 格式的变量引用，可以提取预处理文件或历史执行结果。
"""

import re
import logging
from typing import Any
from .safe_json_dumps import safe_json_dumps

logger = logging.getLogger("django")


def replace_data_markers(obj: Any, state) -> Any:
    """
    递归替换数据标记。
    
    支持两种格式：
    1. ${preprocessed_files.documents.xxx.pdf} - 预处理文件路径
    2. ${action_20250804_123456_789012} - 历史执行结果引用
    
    参数:
    obj: 需要处理的对象（字符串、字典、列表等）
    state: RuntimeState 对象，用于提取数据
    
    返回:
    处理后的对象，其中所有 ${} 标记都被替换为实际数据
    """
    if isinstance(obj, str):
        # 查找 ${路径} 格式的标记
        # 使用标准的 ${} 变量引用格式，LLM 更熟悉
        pattern = r'\$\{([^}]+)\}'
        
        def replacer(match):
            path = match.group(1)
            # logger.info(f"[PLANNER] 正在提取数据路径: {path}")
            
            # 特殊处理 action_id
            if path.startswith('action_'):
                full_data = state.get_full_action_data(path)
                if full_data:
                    tool_output = full_data.get('tool_output', {})
                    result = safe_json_dumps(tool_output)
                    logger.info(f"[PLANNER] 成功提取 action_id {path} 的数据")
                    # logger.info(f"[PLANNER] 数据内容: {result}")
                    return result
                else:
                    logger.warning(f"[PLANNER] 无法找到 action_id: {path}")
                    return f"[数据提取失败: {path}]"
            else:
                # 普通路径
                extracted_data = state.extract_data_by_path(path)
                if extracted_data is not None:
                    if isinstance(extracted_data, str):
                        logger.info(f"[PLANNER] 成功提取路径 {path} 的字符串数据")
                        # logger.info(f"[PLANNER] 数据内容: {extracted_data}")
                        return extracted_data
                    else:
                        result = safe_json_dumps(extracted_data)
                        logger.info(f"[PLANNER] 成功提取路径 {path} 的非字符串数据")
                        # logger.info(f"[PLANNER] 数据内容: {result}")
                        return result
                else:
                    logger.warning(f"[PLANNER] 无法提取数据路径: {path}")
                    return f"[数据提取失败: {path}]"
        
        return re.sub(pattern, replacer, obj)
    elif isinstance(obj, dict):
        return {k: replace_data_markers(v, state) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [replace_data_markers(item, state) for item in obj]
    else:
        return obj