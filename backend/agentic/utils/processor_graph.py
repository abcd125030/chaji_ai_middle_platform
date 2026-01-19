# -*- coding: utf-8 -*-
# backend/agentic/utils/processor_graph.py

"""
处理器图导航模块。

该模块提供了图导航相关的功能，包括节点查找、动态加载可调用对象等。
"""

import importlib
from typing import Dict, Any, Callable, List
from ..core.schemas import PlannerOutput


def load_callable(callable_path: str) -> Callable:
    """
    动态加载 Python 可调用对象（函数或类）。
    例如，给定路径 'backend.tools.advanced.planner.planner_node'，它将加载 `planner_node` 函数。

    参数:
    callable_path (str): 可调用对象的完整导入路径字符串。

    返回:
    Callable: 动态加载的可调用对象。

    抛出:
    ImportError: 如果模块或函数无法找到。
    """
    # 如果路径以 'backend.' 开头，则移除它，以适应 Django 的项目结构
    # 因为 importlib.import_module 通常不需要项目根目录作为前缀
    if callable_path.startswith('backend.'):
        callable_path = callable_path[len('backend.'):]

    # 将路径分割为模块路径和函数/类名称
    module_path, func_name = callable_path.rsplit('.', 1)
    module = importlib.import_module(module_path)  # 导入模块
    return getattr(module, func_name)  # 从模块中获取可调用对象


def find_next_node_name(
    current_node_name: str, 
    node_output: Dict[str, Any], 
    edges_map: Dict[str, List]
) -> str:
    """
    根据当前节点名称和其输出，确定下一个节点的名称。
    此方法遍历当前节点的所有出边，根据边的条件或无条件连接来决定路径。

    参数:
    current_node_name (str): 当前节点的名称。
    node_output (Dict[str, Any]): 当前节点的执行输出。
    edges_map (Dict[str, List]): 边映射字典，键为源节点名称，值为边列表。

    返回:
    str: 下一个节点的名称。

    抛出:
    ValueError: 如果当前节点没有定义出边，或者无法根据输出确定下一个节点。
    """
    if current_node_name == "END":
        return "END"  # 如果当前节点是 "END"，则终止循环

    # 优先使用缓存的edges_map，避免数据库连接问题
    # 在初始化时已经加载了所有的edges到edges_map中
    outgoing_edges = edges_map.get(current_node_name, [])

    if not outgoing_edges:
        raise ValueError(f"Node '{current_node_name}' has no outgoing edges defined.")

    # 优先处理条件边：遍历所有出边，检查是否有匹配条件的边
    for edge in outgoing_edges:
        if edge.condition_key:  # 如果边定义了条件键
            # 处理不同类型的节点输出
            if edge.condition_key:
                # 对于 planner 节点，其输出通常包含 'current_plan'
                if current_node_name == "planner" and isinstance(node_output, dict) and 'current_plan' in node_output:
                    current_plan = node_output['current_plan']
                    if isinstance(current_plan, PlannerOutput):
                        # 特殊处理 CALL_TOOL 动作：条件键格式为 "CALL_TOOL:工具名称"
                        if current_plan.action == "CALL_TOOL" and edge.condition_key == f"CALL_TOOL:{current_plan.tool_name}":
                            return edge.target.name
                        # 如果计划动作直接匹配条件键
                        elif current_plan.action == edge.condition_key:
                            return edge.target.name
                # 对于 output 节点，其输出包含 'output_tool_decision'
                elif current_node_name == "output" and isinstance(node_output, dict) and 'output_tool_decision' in node_output:
                    tool_decision = node_output['output_tool_decision']
                    tool_name = tool_decision.get('tool_name')
                    # 匹配条件键格式 "OUTPUT:工具名称"
                    if tool_name and edge.condition_key == f"OUTPUT:{tool_name}":
                        return edge.target.name
                # 对于字典类型的输出，检查输出中是否存在与 condition_key 匹配的键且其值不为 None
                elif isinstance(node_output, dict) and node_output.get(edge.condition_key) is not None:
                    return edge.target.name

    # 如果没有匹配的条件边，寻找无条件边（即没有 condition_key 的边）
    for edge in outgoing_edges:
        if not edge.condition_key:
            return edge.target.name

    # 如果所有出边都无法匹配，则抛出错误
    raise ValueError(f"Could not determine next node from '{current_node_name}' with output: {node_output}")