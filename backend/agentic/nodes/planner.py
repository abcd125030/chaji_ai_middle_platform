# -*- coding: utf-8 -*-
"""
planner.py

规划器节点模块。负责根据当前运行时状态、可用工具和图结构信息，
利用LLM规划下一步最关键的行动。
"""

import re, json
import logging
from ..utils.logger_config import logger, log_llm_request, log_llm_response
from typing import Dict, Any, Optional

from tools.core.registry import ToolRegistry
from llm.core_service import CoreLLMService
from llm.config_manager import ModelConfigManager
from ..core.schemas import RuntimeState, PlannerOutput
from .components import safe_json_dumps as _safe_json_dumps
from .components import replace_data_markers


def planner_node(state: RuntimeState, nodes_map: Optional[Dict[str, Any]] = None, edges_map: Optional[Dict[str, Any]] = None, 
                 user=None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    规划器节点函数。
    根据当前的运行时状态、可用工具和图结构信息，利用LLM规划下一步最关键的行动。
    它会生成一个包含思考过程、行动类型（调用工具或完成任务）、工具名称和工具输入的规划。

    参数:
    state (RuntimeState): 当前的运行时状态，包含任务目标、行动历史等。
    nodes_map (Optional[Dict[str, Any]]): 包含图中所有节点的字典，用于获取节点配置。
    edges_map (Optional[Dict[str, Any]]): 包含图中所有边的字典，用于格式化图结构信息。
    user: 用户对象（用于日志记录）
    session_id (Optional[str]): 会话ID（用于日志记录）

    返回:
    Dict[str, Any]: 包含LLM生成的当前规划的字典，键为"current_plan"。
    """
    # 检查是否启用链式架构
    import os
    enable_chain = os.getenv('ENABLE_PLANNER_CHAIN', 'true').lower() == 'true'

    
    # 如果不启用链式架构或链式架构失败，使用原始实现
    if not enable_chain:
        logger.info(f"[PLANNER] 使用原始实现处理任务: {state.task_goal[:100]}")
        return _original_planner_implementation(state, nodes_map, edges_map, user, session_id)


def _original_planner_implementation(state: RuntimeState, nodes_map: Optional[Dict[str, Any]] = None, 
                                    edges_map: Optional[Dict[str, Any]] = None, 
                                    user=None, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    原始的planner_node实现
    """
    # 记录规划器开始规划
    logger.info(f"[PLANNER-ORIGINAL] Starting planning for task: {state.task_goal[:100]}")
    try:
        # 实例化核心LLM服务和配置管理器
        core_service = CoreLLMService()
        config_manager = ModelConfigManager()
        
        # 使用统一的模型配置服务获取模型名称
        from agentic.core.model_config_service import NodeModelConfigService
        model_name = NodeModelConfigService.get_model_for_node('planner', nodes_map)
        
        # 获取模型配置（已包含vendor_name）
        model_config = config_manager.get_model_config(model_name)
        
        # 获取一个结构化输出的LLM实例，其输出将严格符合PlannerOutput Pydantic模型
        LLM = core_service.get_structured_llm(
            PlannerOutput, 
            model_config,
            user=user,
            session_id=session_id,
            model_name=model_name,
            source_app='agentic',
            source_function='nodes.planner.planner_node'
        )
        
        # 在函数内部直接构建提示词，不再调用外部函数
        system_prompt, user_prompt = _build_prompt_internal(state, nodes_map)
    except Exception as e:
        logger.error(f"[PLANNER] 构建 prompt 失败: {str(e)}")
        raise
    
    # 打印完整的 prompt 信息用于调试（单个 logger 调用）
    prompt_debug_info = f"""
{"=" * 10}
📊 PLANNER NODE - 完整请求信息
System Prompt 长度: {len(system_prompt)} 字符
User Prompt 长度: {len(user_prompt)} 字符

{"=" * 10}
【System Prompt】
{system_prompt}

{"=" * 10}
【User Prompt】
{user_prompt}
{"=" * 10}
"""
    # 记录LLM请求
    log_llm_request("planner", system_prompt, user_prompt, model_name)
    
    try:
        # 调用 LLM 进行规划，传入系统提示词和用户提示词
        llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt)
        # 记录LLM响应
        log_llm_response("planner", llm_result)
    except Exception as e:
        if "结构化输出解析失败" in str(e):
            logger.warning("[PLANNER] 结构化输出解析失败，重试一次")
            llm_result = LLM.invoke(user_prompt, system_prompt=system_prompt) # 重试一次
        else:
            raise e
    
    # LLM结果已经在上面记录
        
    # 处理 FINISH 时，不再生成 final_answer
    if llm_result.action == "FINISH":
        
        # 清空任何可能由 LLM 填写的 final_answer
        if llm_result.final_answer:
            logger.warning(f"[PLANNER] 警告：Planner 提供了 final_answer，但系统将忽略它")
            llm_result.final_answer = None
            llm_result.title = None
    
    # 如果是调用工具，处理工具输入中的数据引用
    elif llm_result.action == "CALL_TOOL" and llm_result.tool_name:
        tool_input = llm_result.tool_input or {}
        
        # 【自动补充】如果是TodoGenerator工具，自动补充缺失的参数
        if llm_result.tool_name == "TodoGenerator":
            # 补充available_tools参数
            if "available_tools" not in tool_input:
                logger.info("[PLANNER] 检测到TodoGenerator调用，自动补充available_tools参数")
                # 获取工具注册表
                registry = ToolRegistry()
                # 仅获取 libs 类别的工具，并排除 TodoGenerator 自身
                tools_list = registry.list_tools_with_details(category='libs')
                
                # 构造可用工具列表（仅包含libs目录下的执行类工具，排除TodoGenerator）
                available_tools = []
                for tool_info in tools_list:
                    tool_name = tool_info["name"]
                    # 排除 TodoGenerator 自身
                    if tool_name != 'TodoGenerator':
                        available_tools.append({
                            "name": tool_name,
                            "description": tool_info.get("description", "")
                        })
                
                tool_input["available_tools"] = available_tools
                logger.info(f"[PLANNER] 已自动添加 {len(available_tools)} 个可用工具到TodoGenerator参数（仅libs类工具）")
        
        # 替换所有数据标记（调用 components 中的函数）
        # 替换前的tool_input
        tool_input = replace_data_markers(tool_input, state)  # 传入 state 参数
        # 替换后的tool_input
        
        # 更新工具输入
        llm_result.tool_input = tool_input
    
    # 将 plan 添加到行动历史中
    # 提取必要字段并将thought映射为output（统一字段名）
    plan_dict = llm_result.model_dump()
    plan_data = {
        "output": plan_dict.get("thought", ""),  # 统一使用output字段
        "action": plan_dict.get("action", ""),
        "tool_name": plan_dict.get("tool_name"),
        "tool_input": plan_dict.get("tool_input")
    }
    
    # action_history 必须是嵌套列表结构：添加到最后一个子列表（当前对话）
    if not state.action_history:
        # 如果为空，初始化为嵌套结构
        state.action_history = [[{
            "type": "plan",
            "data": plan_data
        }]]
    elif not isinstance(state.action_history[-1], list):
        # 格式不合法
        raise ValueError("action_history 必须是嵌套列表格式")
    else:
        # 添加到最后一个子列表
        state.action_history[-1].append({
            "type": "plan",
            "data": plan_data
        })

    # 记录LLM决策完成的日志信息
    if llm_result.action == "FINISH":
        # 不再在这里添加 final_answer 条目，由 executor 在调用 finalizer_node 后添加
        logger.info(f"[PLANNER FINISH] Action: {llm_result.action}, Tool: {llm_result.tool_name}")
        
        # 输出 output_guidance 信息
        if hasattr(llm_result, 'output_guidance') and llm_result.output_guidance:
            guidance_dict = llm_result.output_guidance.model_dump() if hasattr(llm_result.output_guidance, 'model_dump') else llm_result.output_guidance
            guidance_json = json.dumps(guidance_dict, ensure_ascii=False, indent=2)
            logger.info(f"[PLANNER] output_guidance: {guidance_json}")
        else:
            logger.warning("[PLANNER] 无 output_guidance")
    else:
        # 记录规划器结果
        logger.info(f"""
[PLANNER] 决定使用工具: {llm_result.tool_name}
工具输入:
{_safe_json_dumps(llm_result.tool_input)}
期望输出结构:
{_safe_json_dumps(getattr(llm_result, 'expected_outcome', None))}
""")
    
    return {"current_plan": llm_result} # 返回包含当前规划的字典


# ========== 导出的工具函数 - 供 prompt_builder.py 调用 ==========
# get_tool_descriptions_for_prompt 函数已移至 components/get_tool_descriptions_for_prompt.py
from .components.get_tool_descriptions_for_prompt import get_tool_descriptions_for_prompt


# build_todo_section_for_prompt 函数已移至 components/build_todo_section_for_prompt.py
from .components.build_todo_section_for_prompt import build_todo_section_for_prompt

# # build_task_guidance_for_prompt 函数已移至 components/build_task_guidance_for_prompt.py
# from .components.build_task_guidance_for_prompt import build_task_guidance_for_prompt

# 使用新的基于 action_history 的提示词构建函数
from .components.build_action_history_prompt import build_action_history_prompt

# format_chat_history_for_prompt 函数已移至 components/format_chat_history_for_prompt.py
from .components.format_chat_history_for_prompt import format_chat_history_for_prompt

# get_data_catalog_summary_for_prompt 函数已移至 components/get_data_catalog_summary_for_prompt.py
from .components.get_data_catalog_summary_for_prompt import get_data_catalog_summary_for_prompt

# ========== 原始的内部实现函数 ==========

def _build_prompt_internal(state: RuntimeState, nodes_map: Optional[Dict[str, Any]] = None) -> tuple[str, str]:
    """
    在函数内部构建planner提示词
    
    参数:
    state (RuntimeState): 当前运行时状态
    nodes_map (Optional[Dict[str, Any]]): 节点配置映射
    
    返回:
    tuple[str, str]: (系统提示词, 用户提示词)
    """
    # 调用模块级别的导出函数，保持代码结构一致
    tool_descriptions = get_tool_descriptions_for_prompt()
    # 使用新的基于 action_history 的提示词构建函数
    # 处理嵌套列表结构：只使用当前对话的历史
    current_action_history = state.action_history
    if current_action_history and isinstance(current_action_history[-1], list):
        # 如果是嵌套列表，使用最后一个子列表（当前对话）
        current_action_history = current_action_history[-1]
    
    action_history_prompt = build_action_history_prompt(
        current_action_history,
        format_type="detailed"  # 使用详细格式替代原有的两个历史函数
    )
    data_summary = get_data_catalog_summary_for_prompt(state)
    todo_section = build_todo_section_for_prompt(state)
    # task_guidance = build_task_guidance_for_prompt(state)
    
    # 构建对话历史（如果有）
    chat_history_text = ""
    if state.chat_history:
        chat_history_text = format_chat_history_for_prompt(state.chat_history)
        logger.info(f"[PLANNER] 嵌入历史对话，共 {len(state.chat_history)} 条消息")
    
    # 构建用户信息
    user_info = ""
    if state.user_context:
        user_id = state.user_context.get('user_id', 'unknown')
        username = state.user_context.get('username', 'unknown')
        display_name = state.user_context.get('display_name', username)
        user_info = f"\n当前用户: {display_name} (ID: {user_id})\n"
    
    # 构建系统提示词
    system_prompt = f"""# 智能任务规划器

你负责理解用户需求并智能地选择合适的响应方式。

## 场景识别
- **日常对话**：问候、闲聊等简单交互，直接友好回复即可
- **简单任务**：单一明确的请求，可直接执行工具或给出答案
- **复杂任务**：如果评估任务需要超过3次工具调用才能完成，优先使用 TodoGenerator 创建任务清单

## 核心能力
1. **理解**: 准确判断用户意图（日常对话 vs 任务需求）
2. **规划**: 对于复杂任务，分解为可执行步骤（使用TodoGenerator）
3. **执行**: 调用合适的工具
4. **复用**: 充分利用已有结果
5. **评估**: 判断是否满足需求
6. **适应**: 根据反馈调整计划

## 可用工具详情与使用参数
{tool_descriptions}

## 关于任务完成（FINISH）

- 结合历史步骤理解已经获取的信息，如果足够输出符合用户prompt预期的结果，则选择 FINISH
- 系统会自动收集所有执行历史数据构建上下文，无需你提供具体内容
- 必须提供 output_guidance 输出指导，告诉系统如何组织和呈现答案
- 输出节点会根据任务特征自动选择合适的格式化工具
- 不要滥用知识库工具存储数据，除非是有价值的信息或用户的偏好、习惯、个性化信息

## 输出格式

**只有两种有效的action值：**
1. "CALL_TOOL" - 调用工具执行任务
2. "FINISH" - 完成任务（准备产出回答）

当使用 FINISH 时：
```json
{{
    "thought": "总结已完成的工作和关键发现",
    "action": "FINISH",
    "output_guidance": {{  // 重要：提供输出指导
        "key_points": ["要点1", "要点2"],  // 需要强调的关键要点列表
        "format_requirements": "格式要求（如需要表格、列表、报告等）",
        "quality_requirements": "质量要求（如详细程度、专业性等）",
        "custom_prompt": "任何额外的输出指导或特殊要求"
    }}
}}
```

当使用 CALL_TOOL 时：
```json
{{
    "thought": "你的思考过程",
    "action": "CALL_TOOL",
    "tool_name": "工具名称",
    "tool_input": {{}},  // 工具参数对象
    "expected_outcome": "期望的执行结果"
}}
```
"""
    
    # 构建用户提示词
    user_prompt = f"""## 当前状态信息

### 原始任务
{state._original_task_goal}
{user_info}
{chat_history_text}

### 执行历史
{action_history_prompt}

{data_summary}

{todo_section}

请基于以上信息和你的能力，决定下一步最合适的行动。"""
    
    return system_prompt, user_prompt