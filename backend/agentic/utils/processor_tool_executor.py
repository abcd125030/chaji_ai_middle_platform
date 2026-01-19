# -*- coding: utf-8 -*-
# backend/agentic/utils/processor_tool_executor.py

"""
处理器工具执行模块。

该模块提供了工具执行相关的功能，包括工具调用、配置管理和错误处理。
"""

import json
import logging
from typing import Dict, Any, Optional
from tools.core.registry import ToolRegistry
from ..core.schemas import RuntimeState, PlannerOutput
from ..core.model_config_service import NodeModelConfigService
from .logger_config import logger, log_tool_call, log_tool_result, log_state_change


def execute_tool(state: RuntimeState, 
                 current_plan: PlannerOutput,
                 user_id: Optional[int] = None,
                 nodes_map: Optional[Dict] = None) -> Dict[str, Any]:
    """
    执行工具调用。
    
    参数:
    state (RuntimeState): 当前的运行时状态。
    current_plan (PlannerOutput): 当前的执行计划。
    user_id (Optional[int]): 用户ID。
    nodes_map (Optional[Dict]): 节点映射字典。
    
    返回:
    Dict[str, Any]: 包含工具执行结果的字典。
    
    抛出:
    ValueError: 如果 `current_plan` 无效或缺少工具信息。
    """
    # 检查当前计划是否有效且动作为 "CALL_TOOL"
    if not current_plan or current_plan.action != "CALL_TOOL":
        raise ValueError("Tool executor called without a valid CALL_TOOL plan.")

    tool_name = current_plan.tool_name  # 获取工具名称
    tool_input = current_plan.tool_input  # 获取工具输入参数

    if not tool_name:
        raise ValueError("Tool name is missing in the current plan.")

    registry = ToolRegistry()  # 实例化工具注册表
    try:
        tool_class = registry.get_tool(tool_name)  # 根据名称获取工具类
        
        # 准备工具配置，可以从环境变量或配置文件中读取
        tool_config = get_tool_config(tool_name, nodes_map)
        
        tool_instance = tool_class(config=tool_config)  # 实例化工具并传入配置

        # 确保 tool_input 是字典类型
        if isinstance(tool_input, str):
            # 如果 tool_input 是字符串，尝试解析为 JSON
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                # 如果不是有效的 JSON，将其作为 query 参数
                tool_input = {"query": tool_input}
        
        # 复制 tool_input 以避免修改原始计划数据
        enhanced_tool_input = tool_input.copy() if tool_input else {}
        
        # 确保 enhanced_tool_input 不是 None
        if enhanced_tool_input is None:
            enhanced_tool_input = {}
        
        # 检查工具是否需要访问 runtime state
        if hasattr(tool_instance, 'requires_state_access') and tool_instance.requires_state_access:
            enhanced_tool_input['runtime_state'] = state
        
        # 自动注入或覆盖用户ID
        original_user_id = enhanced_tool_input.get('user_id')
        
        # 优先使用传入的 user_id
        if user_id:
            enhanced_tool_input['user_id'] = user_id
        elif state.user_context:
            # 其次从 user_context 中获取
            context_user_id = state.user_context.get('user_id')
            if context_user_id:
                enhanced_tool_input['user_id'] = context_user_id
            else:
                # 如果user_context存在但没有user_id，这是错误情况
                logger.error(f"user_context中没有user_id，无法为工具 {tool_name} 注入用户ID")
                raise ValueError(f"无法获取用户ID，工具 {tool_name} 需要user_id参数")
        elif 'user_id' not in enhanced_tool_input:
            # 如果没有任何user_id来源，且工具输入中也没有，这是错误情况
            logger.error(f"没有可用的user_id来源，无法为工具 {tool_name} 注入用户ID")
            raise ValueError(f"无法获取用户ID，工具 {tool_name} 需要user_id参数")

        # 记录工具调用
        log_tool_call(tool_name, enhanced_tool_input, user_id)
        
        # 使用工具的统一执行方法 `execute_with_logging`，传递 runtime_state
        tool_output = tool_instance.execute_with_logging(enhanced_tool_input, state)
        
        # 记录工具结果
        log_tool_result(tool_name, tool_output)

        # 记录action_history变化
        old_action_history = state.action_history.copy() if state.action_history else None
        
        # 将 tool_output 添加到行动历史中
        # action_history 必须是嵌套列表结构：添加到最后一个子列表（当前对话）
        if not state.action_history:
            # 如果为空，初始化为嵌套结构
            state.action_history = [[{
                "type": "tool_output",
                "data": tool_output,
                "tool_name": tool_name  # 添加工具名到顶层
            }]]
        elif not isinstance(state.action_history[-1], list):
            # 格式不合法
            raise ValueError("action_history 必须是嵌套列表格式")
        else:
            # 添加到最后一个子列表
            state.action_history[-1].append({
                "type": "tool_output",
                "data": tool_output,
                "tool_name": tool_name  # 添加工具名到顶层
            })
        
        # 记录action_history变化
        if old_action_history != state.action_history:
            log_state_change("action_history", old_action_history, state.action_history, f"tool_executor: {tool_name}")

        return {"tool_output": tool_output}  # 返回工具输出

    except Exception as e:
        # 捕获工具执行过程中发生的任何异常

        # 使用标准化的错误格式构建错误输出
        error_output = {
            "status": "error",
            "message": f"工具执行器异常: {str(e)}",
            "tool_name": tool_name,
            "error_type": type(e).__name__,
            "timestamp": __import__('time').time()  # 记录时间戳
        }

        # 将 tool_output (错误信息) 添加到行动历史中
        # action_history 必须是嵌套列表结构：添加到最后一个子列表（当前对话）
        if not state.action_history:
            # 如果为空，初始化为嵌套结构
            state.action_history = [[{
                "type": "tool_output",
                "data": error_output,
                "tool_name": tool_name  # 添加工具名到顶层
            }]]
        elif not isinstance(state.action_history[-1], list):
            # 格式不合法
            raise ValueError("action_history 必须是嵌套列表格式")
        else:
            # 添加到最后一个子列表
            state.action_history[-1].append({
                "type": "tool_output",
                "data": error_output,
                "tool_name": tool_name  # 添加工具名到顶层
            })

        # 可以在这里添加错误处理逻辑，例如路由到错误处理节点
        return {"tool_output": error_output}


def get_tool_config(tool_name: str, nodes_map: Optional[Dict] = None) -> Dict[str, Any]:
    """
    获取工具的配置。
    
    参数:
    tool_name: 工具名称
    nodes_map: 节点映射字典（可选）
    
    返回:
    Dict[str, Any]: 工具配置字典
    """
    # 使用统一的模型配置服务获取工具配置
    return NodeModelConfigService.get_tool_config(tool_name, nodes_map or {})