# -*- coding: utf-8 -*-
# backend/agentic/utils/processor_state.py

"""
处理器状态管理模块。

该模块提供了运行时状态管理相关的功能，包括加载历史状态、
创建带历史的状态等。
"""

import logging
from typing import List, Dict, Any, Optional
from ..core.schemas import RuntimeState
from ..core.checkpoint import DBCheckpoint
from .commons import user_context

logger = logging.getLogger("django")


def load_session_states(agent_task, checkpoint: DBCheckpoint) -> List[RuntimeState]:
    """
    加载session中所有历史任务的states
    
    参数:
    agent_task: AgentTask实例
    checkpoint: DBCheckpoint实例
    
    返回:
    List[RuntimeState]: 历史任务的状态列表，按时间顺序排列
    """
    if not hasattr(agent_task, 'session_task_history') or not agent_task.session_task_history:
        return []
    
    states = []
    for task_id in agent_task.session_task_history:
        try:
            state = checkpoint.load(str(task_id))
            if state:
                states.append(state)
        except Exception:
            # 如果某个历史状态加载失败，跳过但不中断整个过程
            continue
    
    return states


def create_state_with_history(
    historical_states: List[RuntimeState], 
    new_goal: str, 
    preprocessed_files: Optional[Dict[str, Any]] = None, 
    origin_images: Optional[List[str]] = None, 
    conversation_history: Optional[List[Dict]] = None, 
    usage: Optional[str] = None,
    user_id: Optional[int] = None
) -> RuntimeState:
    """
    基于历史状态创建新的RuntimeState
    
    参数:
    historical_states: 历史状态列表
    new_goal: 新任务目标
    preprocessed_files: 预处理文件
    origin_images: 原始图片路径
    conversation_history: 对话历史
    usage: 使用类型
    user_id: 用户ID
    
    返回:
    RuntimeState: 合并历史信息的新状态
    """
    # 获取用户上下文信息
    user_context_data = user_context(user_id)
    
    # 改为嵌套列表结构：[[第一次对话的历史], [第二次对话的历史], [本次对话的历史（初始为空）]]
    historical_action_lists = []
    combined_context_memory = {}
    combined_chat_history = []  # 合并历史的chat_history
    
    for state in historical_states:
        # Pydantic模型的字段总是存在，只需检查是否为空
        if state.action_history:
            # action_history必须是嵌套列表格式
            if state.action_history and isinstance(state.action_history[0], list):
                historical_action_lists.extend(state.action_history)
            else:
                # 扁平列表格式不合法
                raise ValueError("历史状态中的 action_history 必须是嵌套列表格式")
        if state.context_memory:
            combined_context_memory.update(state.context_memory)
        # 合并历史的chat_history
        if state.chat_history:
            combined_chat_history.extend(state.chat_history)
    
    # 为当前对话添加一个空列表
    historical_action_lists.append([])
    
    # 只保留最近的10轮对话历史
    if len(historical_action_lists) > 10:
        historical_action_lists = historical_action_lists[-10:]
    
    # 处理对话历史
    enhanced_task_goal = new_goal
    # 使用合并的历史chat_history，如果没有则使用传入的conversation_history
    # 注意：conversation_history是前端传入的，combined_chat_history是从历史状态恢复的
    # 优先使用从历史状态恢复的完整对话历史
    complete_chat_history = combined_chat_history if combined_chat_history else (list(conversation_history) if conversation_history else [])
    
    # 生成历史对话上下文（用于任务目标的增强）
    if complete_chat_history:
        history_context = "\n".join([
            f"{'用户' if msg.get('role') == 'user' else 'AI助手'}: {msg.get('content', '')}"
            for msg in complete_chat_history
            if msg.get('content')
        ])
        if history_context:
            enhanced_task_goal = f"历史对话上下文：\n{history_context}\n\n当前任务：{new_goal}"
    
    # 将当前用户的输入添加到对话历史
    complete_chat_history.append({
        "role": "user",
        "content": new_goal
    })
    
    return RuntimeState(
        task_goal=enhanced_task_goal,
        preprocessed_files=preprocessed_files or {'documents': {}, 'tables': {}, 'images': {}, 'other_files': {}},
        origin_images=origin_images or [],
        usage=usage,
        action_history=historical_action_lists,
        context_memory=combined_context_memory,
        user_context=user_context_data or {},
        chat_history=complete_chat_history  # 保存包含当前输入的完整对话历史
    )


def create_initial_state(
    initial_task_goal: str,
    preprocessed_files: Optional[Dict[str, Any]] = None,
    origin_images: Optional[List[str]] = None,
    conversation_history: Optional[List[Dict]] = None,
    usage: Optional[str] = None,
    user_id: Optional[int] = None
) -> RuntimeState:
    """
    创建初始运行时状态
    
    参数:
    initial_task_goal: 初始任务目标
    preprocessed_files: 预处理文件
    origin_images: 原始图片路径
    conversation_history: 对话历史
    usage: 使用类型
    user_id: 用户ID
    
    返回:
    RuntimeState: 初始状态
    """
    enhanced_task_goal = initial_task_goal
    # 准备完整的对话历史（包含本次用户输入）
    complete_chat_history = list(conversation_history) if conversation_history else []
    
    if conversation_history:
        # 将历史对话转换为文本上下文
        history_context = "\n".join([
            f"{'用户' if msg.get('role') == 'user' else 'AI助手'}: {msg.get('content', '')}"
            for msg in conversation_history
            if msg.get('content')
        ])
        if history_context:
            enhanced_task_goal = f"历史对话上下文：\n{history_context}\n\n当前任务：{initial_task_goal}"
    
    # 将当前用户的输入添加到对话历史
    complete_chat_history.append({
        "role": "user",
        "content": initial_task_goal
    })
    
    # 获取用户上下文信息
    user_context_data = user_context(user_id)
    
    return RuntimeState(
        task_goal=enhanced_task_goal,
        preprocessed_files=preprocessed_files,
        origin_images=origin_images,
        usage=usage,
        user_context=user_context_data,
        chat_history=complete_chat_history,  # 保存包含当前输入的完整对话历史
        action_history=[[]]  # 初始化为嵌套列表结构，准备接收第一个对话的动作
    )