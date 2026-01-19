# -*- coding: utf-8 -*-
"""
Agentic 模块统一日志配置

此模块提供统一的日志记录功能，专注于记录：
1. LLM调用请求和响应
2. State字段值变化
3. 关键执行步骤
"""

import logging
import json
from typing import Any, Dict, Optional

# 创建专用的logger
logger = logging.getLogger('agentic')

def log_llm_request(node_name: str, system_prompt: str, user_prompt: str, model_name: str = None):
    """
    记录LLM调用请求
    
    Args:
        node_name: 调用节点名称
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        model_name: 模型名称
    """
    logger.info(f"""
=============== LLM REQUEST [{node_name}] ===============
Model: {model_name or 'default'}
System Prompt Length: {len(system_prompt)} chars
User Prompt Length: {len(user_prompt)} chars

--- System Prompt ---
{system_prompt}

--- User Prompt ---
{user_prompt}
=========================================================
""")

def log_llm_response(node_name: str, response: Any):
    """
    记录LLM响应结果
    
    Args:
        node_name: 调用节点名称
        response: LLM响应结果
    """
    # 尝试序列化响应
    if hasattr(response, 'model_dump'):
        response_str = json.dumps(response.model_dump(), ensure_ascii=False, indent=2)
    elif hasattr(response, 'dict'):
        response_str = json.dumps(response.dict(), ensure_ascii=False, indent=2)
    elif isinstance(response, dict):
        response_str = json.dumps(response, ensure_ascii=False, indent=2)
    else:
        response_str = str(response)
    
    logger.info(f"""
=============== LLM RESPONSE [{node_name}] ===============
{response_str}
==========================================================
""")

def log_state_change(field_name: str, old_value: Any, new_value: Any, context: str = ""):
    """
    记录State字段值变化
    
    Args:
        field_name: 字段名称
        old_value: 旧值
        new_value: 新值
        context: 上下文信息
    """
    # 处理复杂对象的序列化
    def serialize_value(value):
        if value is None:
            return "None"
        elif isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        elif hasattr(value, 'model_dump'):
            return json.dumps(value.model_dump(), ensure_ascii=False, indent=2)
        elif hasattr(value, 'dict'):
            return json.dumps(value.dict(), ensure_ascii=False, indent=2)
        else:
            return str(value)
    
    old_str = serialize_value(old_value)
    new_str = serialize_value(new_value)
    
    logger.info(f"""
=============== STATE CHANGE [{field_name}] ===============
Context: {context}

--- Old Value ---
{old_str}

--- New Value ---
{new_str}
============================================================
""")

def log_tool_call(tool_name: str, tool_input: Dict[str, Any], user_id: Optional[int] = None):
    """
    记录工具调用
    
    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数
        user_id: 用户ID
    """
    input_str = json.dumps(tool_input, ensure_ascii=False, indent=2)
    logger.info(f"""
=============== TOOL CALL [{tool_name}] ===============
User ID: {user_id}
Input Parameters:
{input_str}
========================================================
""")

def log_tool_result(tool_name: str, result: Dict[str, Any]):
    """
    记录工具执行结果
    
    Args:
        tool_name: 工具名称
        result: 执行结果
    """
    result_str = json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, dict) else str(result)
    logger.info(f"""
=============== TOOL RESULT [{tool_name}] ===============
{result_str}
==========================================================
""")

def log_execution_step(step_name: str, task_id: str = None, **kwargs):
    """
    记录执行步骤
    
    Args:
        step_name: 步骤名称
        task_id: 任务ID
        **kwargs: 其他相关信息
    """
    extra_info = json.dumps(kwargs, ensure_ascii=False, indent=2) if kwargs else ""
    logger.info(f"""
=============== EXECUTION STEP [{step_name}] ===============
Task ID: {task_id}
{extra_info}
=============================================================
""")